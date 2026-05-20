from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import threading
from typing import Callable

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

VK_CODES = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46, "g": 0x47,
    "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E,
    "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54, "u": 0x55,
    "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
}

class NativeHotKeyListener:
    """Uses the Windows hotkey API instead of keyboard hooks."""

    def __init__(self, bindings: dict[str, Callable[[], None]]) -> None:
        self.bindings = bindings
        self.thread: threading.Thread | None = None
        self.thread_id = 0
        self.failed_hotkeys: list[str] = []
        self._callbacks: dict[int, Callable[[], None]] = {}

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

    def _run(self) -> None:
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered_ids: list[int] = []
        for hotkey_id, (hotkey, callback) in enumerate(self.bindings.items(), start=1):
            parsed = self._parse_hotkey(hotkey)
            if parsed is None:
                logging.error("Unsupported hotkey syntax: %s", hotkey)
                self.failed_hotkeys.append(hotkey)
                continue
            modifiers, vk_code = parsed
            if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code):
                error = ctypes.windll.kernel32.GetLastError()
                if error == ERROR_HOTKEY_ALREADY_REGISTERED:
                    logging.error("Hotkey already registered by another app: %s", hotkey)
                else:
                    logging.error("Failed to register hotkey %s. Windows error: %s", hotkey, error)
                self.failed_hotkeys.append(hotkey)
                continue
            self._callbacks[hotkey_id] = callback
            registered_ids.append(hotkey_id)
            logging.info("Registered native hotkey: %s", hotkey)

        msg = ctypes.wintypes.MSG()
        try:
            while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    callback = self._callbacks.get(int(msg.wParam))
                    if callback is not None:
                        try:
                            callback()
                        except Exception:
                            logging.exception("Hotkey callback failed")
        finally:
            for hotkey_id in registered_ids:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)

    @staticmethod
    def _parse_hotkey(hotkey: str) -> tuple[int, int] | None:
        modifiers = 0
        key = ""
        for part in hotkey.lower().split("+"):
            part = part.strip()
            if part == "<ctrl>":
                modifiers |= MOD_CONTROL
            elif part == "<alt>":
                modifiers |= MOD_ALT
            elif part == "<shift>":
                modifiers |= MOD_SHIFT
            elif part.startswith("<") and part.endswith(">"):
                return None
            else:
                key = part
        vk_code = VK_CODES.get(key)
        if not key or vk_code is None:
            return None
        return modifiers, vk_code
