from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from logging.handlers import RotatingFileHandler

from spell_assistant.config import LOG_FILE, APP_TITLE

MB_ICONINFORMATION = 0x40
ERROR_ALREADY_EXISTS = 183
INSTANCE_MUTEX_NAME = "Local\\AIAgentChatSpellAssistant"
INSTANCE_MUTEX_HANDLE = None
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

def _cursor_position() -> tuple[int, int]:
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

def _safe_call(default, fn, *args):
    try:
        return fn(*args)
    except Exception:
        return default

import sys
import os

def get_asset_path(filename: str) -> str:
    """Get the absolute path to an asset, handling PyInstaller's _MEIPASS."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'assets', filename)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', filename)

def set_app_user_model_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIAgentChat.SpellAssistant")
    except Exception as e:
        import logging
        logging.warning("Could not set AppUserModelID: %s", e)

def configure_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)

def ensure_single_instance() -> bool:
    global INSTANCE_MUTEX_HANDLE
    INSTANCE_MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, INSTANCE_MUTEX_NAME)
    if not INSTANCE_MUTEX_HANDLE:
        return True
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            None,
            "AI Agent Chat Spell Assistant is already running.\n\nUse the tray icon to scan, pause, or exit it.",
            APP_TITLE,
            MB_ICONINFORMATION,
        )
        return False
    return True
