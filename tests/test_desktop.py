import asyncio
import os
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from aion_healer.core import Member, Rule
from aion_healer.desktop import foreground_process, require_x11
from aion_healer.portal import KEYS, PortalDesktop


class DesktopTests(unittest.TestCase):
    def test_wayland_never_uses_x11_automation(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}):
            with self.assertRaisesRegex(RuntimeError, "Wayland"):
                require_x11()

    def test_wayland_focus_missing_tool_fails_closed(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), patch("subprocess.check_output", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RuntimeError, "kdotool"):
                foreground_process()

    def test_portal_does_not_send_when_focus_lost(self):
        portal = object.__new__(PortalDesktop)
        portal.closed = threading.Event()
        portal.focused = Mock(return_value=False)
        portal.submit = Mock()
        self.assertFalse(portal.cast(Member("a", "f1", (), ()), Rule(30, "1", 8), "game", threading.Event()))
        portal.submit.assert_not_called()

    def test_evdev_key_mapping(self):
        self.assertEqual([KEYS[k] for k in ["f1", "f10", "f11", "f12", "1", "q", "a"]], [59, 68, 87, 88, 2, 16, 30])


class PortalTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_is_released_even_on_cancellation(self):
        portal = object.__new__(PortalDesktop)
        portal.session = "/test"
        portal.remote = Mock()
        portal.remote.call_notify_keyboard_keycode = AsyncMock()
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await portal.key(59)
        self.assertEqual([call.args[-1] for call in portal.remote.call_notify_keyboard_keycode.call_args_list], [1, 0])

    async def test_permission_denial_is_not_success(self):
        portal = object.__new__(PortalDesktop)
        portal.loop = asyncio.get_running_loop()
        portal.bus = Mock(unique_name=":1.7")
        portal.requests = {}
        async def call(options):
            path = "/org/freedesktop/portal/desktop/request/1_7/" + options["handle_token"].value
            portal.requests[path].set_result((1, {}))
            return path
        with self.assertRaisesRegex(RuntimeError, "cancelado ou negado"):
            await portal.request(call, {})
        self.assertEqual(portal.requests, {})

    async def test_response_before_method_returns_is_received(self):
        from dbus_next import Variant
        portal = object.__new__(PortalDesktop)
        portal.loop = asyncio.get_running_loop()
        portal.bus = Mock(unique_name=":1.7")
        portal.requests = {}
        async def call(options):
            path = "/org/freedesktop/portal/desktop/request/1_7/" + options["handle_token"].value
            portal.requests[path].set_result((0, {"devices": Variant("u", 1)}))
            return path
        self.assertEqual(await portal.request(call, {}), {"devices": 1})


if __name__ == "__main__":
    unittest.main()
