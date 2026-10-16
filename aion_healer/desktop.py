import os
from pathlib import Path
import re
import subprocess
import sys


def require_x11():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Esta versão requer Linux com sessão X11.")
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError("Sessão Wayland detectada. Esta versão requer entrar em uma sessão X11/Xorg.")
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Nenhum desktop X11 disponível (DISPLAY ausente). Use o desktop local.")


def foreground_process():
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        try:
            result = subprocess.check_output(["kdotool", "getactivewindow", "getwindowpid"], text=True, timeout=3)
        except FileNotFoundError as exc:
            raise RuntimeError("O envio em Wayland requer KDE Plasma 6 e kdotool para verificar o foco. A simulação continua disponível.") from exc
        if not result.strip().isdigit():
            return None
        return Path(f"/proc/{int(result.strip())}/comm").read_text().strip()
    active = subprocess.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True, timeout=2)
    match = re.search(r"0x[0-9a-fA-F]+", active)
    if not match or int(match[0], 16) == 0:
        return None
    info = subprocess.check_output(["xprop", "-id", match[0], "_NET_WM_PID"], text=True, timeout=2)
    pid = re.search(r"=\s*(\d+)", info)
    if not pid:
        return None
    return Path(f"/proc/{pid[1]}/comm").read_text().strip()


class X11Desktop:
    def __init__(self):
        require_x11()
        import pyautogui
        self.io = pyautogui
        self.io.FAILSAFE = True
        self.io.PAUSE = 0.1

    def screenshot(self):
        from PIL import ImageGrab
        return ImageGrab.grab(xdisplay=os.environ["DISPLAY"])

    def valid_key(self, key):
        return key in self.io.KEYBOARD_KEYS

    def focused(self, process):
        return bool(process) and (foreground_process() or "").casefold() == process.casefold()

    def cast(self, member, rule, process, stop):
        if stop.is_set() or not self.focused(process):
            return False
        self.io.press(member.target_key)
        if stop.wait(0.15) or not self.focused(process):
            return False
        self.io.press(rule.key)
        return True

    def close(self):
        pass


def Desktop():
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        from .portal import PortalDesktop
        return PortalDesktop()
    return X11Desktop()
