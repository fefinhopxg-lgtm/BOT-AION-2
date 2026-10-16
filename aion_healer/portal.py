"""Wayland screen and keyboard session authorized by xdg-desktop-portal.

Uses the compositor's consent dialog; no root, uinput or compositor bypass.
"""
import asyncio
import concurrent.futures
import os
import threading
import uuid

from PIL import Image


KEYS = {**dict(zip("1234567890", range(2, 12))),
        **dict(zip("qwertyuiop", range(16, 26))),
        **dict(zip("asdfghjkl", range(30, 39))),
        **dict(zip("zxcvbnm", range(44, 51))),
        **{f"f{i}": 58 + i for i in range(1, 11)},
        "f11": 87, "f12": 88, "space": 57, "enter": 28,
        "esc": 1, "tab": 15, "up": 103, "down": 108,
        "left": 105, "right": 106, "-": 12, "=": 13}


class PortalDesktop:
    def __init__(self):
        try:
            import gi
            gi.require_version("Gst", "1.0")
            gi.require_version("GstVideo", "1.0")
            from gi.repository import Gst
            import dbus_next  # noqa: F401
        except (ImportError, ValueError) as exc:
            raise RuntimeError("Wayland requer PyGObject/GStreamer do sistema e dbus-next. Consulte README.md.") from exc
        self.Gst = Gst
        Gst.init(None)
        self.closed = threading.Event()
        self.pipeline = None
        self.bus = None
        self.session = None
        self.fd = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        try:
            self.submit(self.open(), timeout=180)
        except Exception:
            self.close()
            raise

    def submit(self, coroutine, timeout=10):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise RuntimeError("O portal não respondeu a tempo. Autorize a sessão no desktop e tente novamente.")

    async def request(self, call, *args):
        from dbus_next import Variant
        token = "aion_" + uuid.uuid4().hex
        unique = self.bus.unique_name[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{unique}/{token}"
        future = self.loop.create_future()
        self.requests[path] = future
        options = dict(args[-1])
        options["handle_token"] = Variant("s", token)
        try:
            actual = await call(*args[:-1], options)
            if actual != path:
                raise RuntimeError("O portal retornou um identificador inesperado.")
            code, results = await asyncio.wait_for(future, timeout=170)
            if code != 0:
                raise RuntimeError("Compartilhamento cancelado ou negado pelo desktop.")
            return {key: value.value for key, value in results.items()}
        finally:
            self.requests.pop(path, None)

    async def open(self):
        from dbus_next import Message, MessageType, Variant
        from dbus_next.aio import MessageBus
        self.requests = {}
        self.bus = await MessageBus(negotiate_unix_fd=True).connect()
        def received(message):
            if message.message_type != MessageType.SIGNAL:
                return
            if message.interface == "org.freedesktop.portal.Request" and message.member == "Response":
                future = self.requests.get(message.path)
                if future and not future.done():
                    future.set_result(message.body)
            elif message.interface == "org.freedesktop.portal.Session" and message.member == "Closed":
                if message.path == self.session:
                    self.closed.set()
        self.bus.add_message_handler(received)
        for interface in ("org.freedesktop.portal.Request", "org.freedesktop.portal.Session"):
            reply = await self.bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus", member="AddMatch", signature="s",
                body=[f"type='signal',interface='{interface}'"]))
            if reply.message_type == MessageType.ERROR:
                raise RuntimeError("Não foi possível observar respostas do portal.")
        introspection = await self.bus.introspect("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
        proxy = self.bus.get_proxy_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", introspection)
        self.remote = proxy.get_interface("org.freedesktop.portal.RemoteDesktop")
        screen = proxy.get_interface("org.freedesktop.portal.ScreenCast")
        created = await self.request(self.remote.call_create_session, {"session_handle_token": Variant("s", "aion_" + uuid.uuid4().hex)})
        self.session = created["session_handle"]
        await self.request(self.remote.call_select_devices, self.session, {"types": Variant("u", 1)})
        await self.request(screen.call_select_sources, self.session, {"types": Variant("u", 1), "multiple": Variant("b", False), "cursor_mode": Variant("u", 1)})
        started = await self.request(self.remote.call_start, self.session, "", {})
        if not started.get("devices", 0) & 1:
            raise RuntimeError("O portal não concedeu acesso ao teclado.")
        streams = started.get("streams", [])
        if len(streams) != 1:
            raise RuntimeError("Selecione exatamente um monitor no diálogo de compartilhamento.")
        self.fd = await screen.call_open_pipe_wire_remote(self.session, {})
        node = int(streams[0][0])
        self.pipeline = self.Gst.parse_launch(
            f"pipewiresrc fd={self.fd} path={node} do-timestamp=true ! videoconvert ! "
            "video/x-raw,format=RGB ! appsink name=frames sync=false max-buffers=1 drop=true")
        self.sink = self.pipeline.get_by_name("frames")
        if self.pipeline.set_state(self.Gst.State.PLAYING) == self.Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Não foi possível iniciar a captura PipeWire.")

    def screenshot(self):
        if self.closed.is_set():
            raise RuntimeError("A sessão de compartilhamento foi encerrada pelo desktop.")
        sample = self.sink.emit("try-pull-sample", 3 * self.Gst.SECOND)
        if sample is None:
            raise RuntimeError("Nenhum quadro PipeWire recebido. Verifique o compartilhamento do monitor.")
        from gi.repository import GstVideo
        info = GstVideo.VideoInfo.new_from_caps(sample.get_caps())
        buffer = sample.get_buffer()
        ok, mapping = buffer.map(self.Gst.MapFlags.READ)
        if not ok:
            raise RuntimeError("Não foi possível ler o quadro PipeWire.")
        try:
            return Image.frombytes("RGB", (info.width, info.height), bytes(mapping.data), "raw", "RGB", info.stride[0], 1)
        finally:
            buffer.unmap(mapping)

    def valid_key(self, key):
        return key in KEYS

    def focused(self, process):
        from .desktop import foreground_process
        return bool(process) and (foreground_process() or "").casefold() == process.casefold()

    async def key(self, code):
        await self.remote.call_notify_keyboard_keycode(self.session, {}, code, 1)
        try:
            await asyncio.sleep(0.03)
        finally:
            await self.remote.call_notify_keyboard_keycode(self.session, {}, code, 0)

    def cast(self, member, rule, process, stop):
        if self.closed.is_set() or stop.is_set() or not self.focused(process):
            return False
        self.submit(self.key(KEYS[member.target_key]))
        if stop.wait(0.15) or not self.focused(process):
            return False
        self.submit(self.key(KEYS[rule.key]))
        return True

    async def disconnect(self):
        try:
            if self.bus and self.session:
                from dbus_next import Message
                await self.bus.call(Message(destination="org.freedesktop.portal.Desktop", path=self.session,
                    interface="org.freedesktop.portal.Session", member="Close"))
        finally:
            if self.bus:
                self.bus.disconnect()

    def close(self):
        self.closed.set()
        if self.pipeline:
            self.pipeline.set_state(self.Gst.State.NULL)
        if self.loop.is_running():
            try:
                self.submit(self.disconnect(), timeout=3)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
