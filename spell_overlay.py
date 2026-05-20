from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import logging
from logging.handlers import RotatingFileHandler
import re
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pyperclip
import pystray
import uiautomation as auto
from PIL import Image, ImageDraw
from pynput import keyboard
from spellchecker import SpellChecker


WORD_RE = re.compile(r"[A-Za-z][A-Za-z']{1,}")
APP_TITLE = "AI Chat Spell Assistant"
APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "spell_overlay.log"
HOTKEY_SCAN = "<ctrl>+<alt>+s"
HOTKEY_CLIPBOARD_SCAN = "<ctrl>+<alt>+<shift>+s"
HOTKEY_DIAGNOSTICS = "<ctrl>+<alt>+d"
HOTKEY_PAUSE = "<ctrl>+<alt>+p"
HOTKEY_HIDE = "<esc>"
CLIPBOARD_COPY_DELAY_SECONDS = 0.05
CLIPBOARD_FOCUS_DELAY_SECONDS = 0.08
CLIPBOARD_PASTE_DELAY_SECONDS = 0.04
CLIPBOARD_WAIT_TIMEOUT_SECONDS = 0.8
USER_WORDS_FILE = APP_DIR / "user_words.txt"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DEFAULT_KNOWN_WORDS = {
    "api",
    "chatgpt",
    "codex",
    "electron",
    "github",
    "javascript",
    "json",
    "monaco",
    "npm",
    "openai",
    "powershell",
    "python",
    "typescript",
    "uiautomation",
    "vscode",
}

DEFAULT_TARGET_KEYWORDS = [
    "antigravity",
    "chatgpt",
    "codex",
    "openai",
    "ai chat",
    "ai agent",
    "ask ai",
    "ask codex",
    "agent chat",
]
DEFAULT_DEDICATED_AI_PROCESSES = [
    "antigravity.exe",
    "chatgpt.exe",
    "codex.exe",
]


@dataclass
class AppConfig:
    hotkey_scan: str = HOTKEY_SCAN
    hotkey_clipboard_scan: str = HOTKEY_CLIPBOARD_SCAN
    hotkey_diagnostics: str = HOTKEY_DIAGNOSTICS
    hotkey_pause: str = HOTKEY_PAUSE
    hotkey_hide: str = HOTKEY_HIDE
    clipboard_copy_delay_seconds: float = CLIPBOARD_COPY_DELAY_SECONDS
    clipboard_focus_delay_seconds: float = CLIPBOARD_FOCUS_DELAY_SECONDS
    clipboard_paste_delay_seconds: float = CLIPBOARD_PASTE_DELAY_SECONDS
    clipboard_wait_timeout_seconds: float = CLIPBOARD_WAIT_TIMEOUT_SECONDS
    startup_message: bool = True
    extra_known_words: list[str] = field(default_factory=list)
    target_keywords: list[str] = field(default_factory=lambda: DEFAULT_TARGET_KEYWORDS.copy())
    dedicated_ai_process_names: list[str] = field(default_factory=lambda: DEFAULT_DEDICATED_AI_PROCESSES.copy())
    clipboard_first_for_ai_chat: bool = True
    max_chat_input_chars: int = 12000

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "AppConfig":
        defaults = cls()
        if not path.exists():
            path.write_text(json.dumps(defaults.to_json(), indent=2) + "\n", encoding="utf-8")
            return defaults

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to read settings.json; using defaults")
            return defaults
        if not isinstance(raw, dict):
            logging.warning("settings.json did not contain an object; using defaults")
            return defaults

        values = defaults.to_json()
        values.update({key: value for key, value in raw.items() if key in values})
        config = cls(**values)
        if raw != config.to_json():
            path.write_text(json.dumps(config.to_json(), indent=2) + "\n", encoding="utf-8")
        return config

    def to_json(self) -> dict[str, object]:
        return {
            "hotkey_scan": self.hotkey_scan,
            "hotkey_clipboard_scan": self.hotkey_clipboard_scan,
            "hotkey_diagnostics": self.hotkey_diagnostics,
            "hotkey_pause": self.hotkey_pause,
            "hotkey_hide": self.hotkey_hide,
            "clipboard_copy_delay_seconds": self.clipboard_copy_delay_seconds,
            "clipboard_focus_delay_seconds": self.clipboard_focus_delay_seconds,
            "clipboard_paste_delay_seconds": self.clipboard_paste_delay_seconds,
            "clipboard_wait_timeout_seconds": self.clipboard_wait_timeout_seconds,
            "startup_message": self.startup_message,
            "extra_known_words": self.extra_known_words,
            "target_keywords": self.target_keywords,
            "dedicated_ai_process_names": self.dedicated_ai_process_names,
            "clipboard_first_for_ai_chat": self.clipboard_first_for_ai_chat,
            "max_chat_input_chars": self.max_chat_input_chars,
        }


@dataclass
class TextSnapshot:
    text: str
    source_name: str
    setter: Callable[[str], bool] | None
    extraction_method: str
    replace_note: str | None = None


@dataclass
class Misspelling:
    word: str
    start: int
    end: int
    suggestions: list[str]


@dataclass
class ActiveWindowInfo:
    hwnd: int
    title: str
    process_id: int
    process_name: str
    process_path: str
    focused_name: str
    focused_control_type: str
    focused_class_name: str
    focused_automation_id: str


@dataclass
class TargetMatch:
    allowed: bool
    reason: str
    info: ActiveWindowInfo


def _cursor_position() -> tuple[int, int]:
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _safe_call(default, fn, *args):
    try:
        return fn(*args)
    except Exception:
        return default


def configure_logging() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)


class WindowTargetGuard:
    """Allows scans only when the foreground window looks like an AI chat target."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def match_active_target(self) -> TargetMatch:
        info = self.active_window_info()
        process_name = info.process_name.lower()
        dedicated_processes = {item.lower() for item in self.config.dedicated_ai_process_names}
        if process_name and process_name in dedicated_processes:
            return TargetMatch(True, f"dedicated AI process: {info.process_name}", info)

        haystack = "\n".join(
            [
                info.title,
                info.focused_name,
                info.focused_control_type,
                info.focused_class_name,
                info.focused_automation_id,
            ]
        ).lower()
        for keyword in self.config.target_keywords:
            normalized = keyword.strip().lower()
            if normalized and normalized in haystack:
                return TargetMatch(True, f"AI chat keyword: {keyword}", info)

        return TargetMatch(False, "active window/control did not match AI chat targets", info)

    def describe_active_target(self) -> str:
        match = self.match_active_target()
        info = match.info
        return "\n".join(
            [
                f"AI chat target: {'yes' if match.allowed else 'no'}",
                f"Reason: {match.reason}",
                f"Window title: {info.title or '(empty)'}",
                f"Process: {info.process_name or '(unknown)'}",
                f"Process path: {info.process_path or '(unknown)'}",
                f"Focused name: {info.focused_name or '(empty)'}",
                f"Focused type: {info.focused_control_type or '(unknown)'}",
                f"Focused class: {info.focused_class_name or '(unknown)'}",
                f"Focused AutomationId: {info.focused_automation_id or '(empty)'}",
            ]
        )

    def active_window_info(self) -> ActiveWindowInfo:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        process_id = self._window_process_id(hwnd)
        process_path = self._process_path(process_id)
        process_name = Path(process_path).name if process_path else ""
        control = _safe_call(None, auto.GetFocusedControl)
        return ActiveWindowInfo(
            hwnd=hwnd,
            title=self._window_title(hwnd),
            process_id=process_id,
            process_name=process_name,
            process_path=process_path,
            focused_name=_safe_call("", lambda: control.Name) if control else "",
            focused_control_type=_safe_call("", lambda: control.ControlTypeName) if control else "",
            focused_class_name=_safe_call("", lambda: control.ClassName) if control else "",
            focused_automation_id=_safe_call("", lambda: control.AutomationId) if control else "",
        )

    @staticmethod
    def _window_title(hwnd: int) -> str:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    @staticmethod
    def _window_process_id(hwnd: int) -> int:
        process_id = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value)

    @staticmethod
    def _process_path(process_id: int) -> str:
        if not process_id:
            return ""
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        if not handle:
            return ""
        try:
            size = ctypes.wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return ""
        finally:
            kernel32.CloseHandle(handle)


class AccessibilityReader:
    """Reads the currently focused Windows UI Automation control."""

    def read_focused_text(self) -> TextSnapshot | None:
        control = _safe_call(None, auto.GetFocusedControl)
        if control is None:
            return None

        source_name = _safe_call("Focused control", lambda: control.Name) or "Focused control"

        value_pattern = _safe_call(None, control.GetValuePattern)
        if value_pattern is not None:
            value = _safe_call("", lambda: value_pattern.Value)
            if value:
                return TextSnapshot(value, source_name, self._value_setter(value_pattern), "UI Automation ValuePattern")

        text_pattern = _safe_call(None, control.GetTextPattern)
        if text_pattern is not None:
            document_range = _safe_call(None, lambda: text_pattern.DocumentRange)
            if document_range is not None:
                text = _safe_call("", document_range.GetText, -1)
                if text:
                    return TextSnapshot(text, source_name, None, "UI Automation TextPattern")

        fallback = _safe_call("", lambda: control.Name)
        if fallback:
            return TextSnapshot(fallback, source_name, None, "UI Automation Name")

        return None

    @staticmethod
    def _value_setter(value_pattern) -> Callable[[str], bool]:
        def set_value(new_value: str) -> bool:
            try:
                value_pattern.SetValue(new_value)
                return True
            except Exception:
                return False

        return set_value

    def describe_focused_control(self) -> str:
        control = _safe_call(None, auto.GetFocusedControl)
        if control is None:
            return "No focused control was available through UI Automation."

        lines = [
            f"Name: {_safe_call('', lambda: control.Name) or '(empty)'}",
            f"Control type: {_safe_call('', lambda: control.ControlTypeName) or '(unknown)'}",
            f"Class: {_safe_call('', lambda: control.ClassName) or '(unknown)'}",
            f"AutomationId: {_safe_call('', lambda: control.AutomationId) or '(empty)'}",
            f"ProcessId: {_safe_call('', lambda: control.ProcessId) or '(unknown)'}",
            f"ValuePattern: {'yes' if _safe_call(None, control.GetValuePattern) else 'no'}",
            f"TextPattern: {'yes' if _safe_call(None, control.GetTextPattern) else 'no'}",
        ]
        return "\n".join(lines)


class ClipboardFieldReader:
    """Fallback reader for custom editors that hide text from accessibility APIs."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.keyboard = keyboard.Controller()

    def read_focused_field(self) -> TextSnapshot | None:
        control = _safe_call(None, auto.GetFocusedControl)
        source_name = self._source_name(control)
        previous_clipboard = self._paste_text()
        marker = f"__SPELL_OVERLAY_MARKER_{time.monotonic_ns()}__"

        try:
            if not self._copy_text(marker):
                return None
            copied_text = self._wait_for_clipboard_text(marker)
        finally:
            self._restore_clipboard(previous_clipboard)

        if not copied_text or copied_text == marker or not copied_text.strip():
            return None
        if len(copied_text) > self.config.max_chat_input_chars:
            logging.warning("Rejected clipboard text with %s chars; likely not a chat input", len(copied_text))
            return None

        return TextSnapshot(
            copied_text,
            source_name,
            self._field_replacer(control),
            "AI chat clipboard input",
            "Replacement uses Ctrl+A/V inside the focused AI chat input.",
        )

    def _copy_text(self, marker: str) -> bool:
        try:
            pyperclip.copy(marker)
            time.sleep(self.config.clipboard_copy_delay_seconds)
            self._combo(keyboard.Key.ctrl, "a")
            time.sleep(self.config.clipboard_copy_delay_seconds)
            self._combo(keyboard.Key.ctrl, "c")
            return True
        except Exception:
            return False

    def _field_replacer(self, control) -> Callable[[str], bool]:
        def replace_text(new_text: str) -> bool:
            previous_clipboard = self._paste_text()
            try:
                if control is None:
                    return False
                control.SetFocus()
                time.sleep(self.config.clipboard_focus_delay_seconds)
                pyperclip.copy(new_text)
                time.sleep(self.config.clipboard_paste_delay_seconds)
                self._combo(keyboard.Key.ctrl, "a")
                time.sleep(self.config.clipboard_paste_delay_seconds)
                self._combo(keyboard.Key.ctrl, "v")
                time.sleep(0.12)
                return True
            except Exception:
                return False
            finally:
                self._restore_clipboard(previous_clipboard)

        return replace_text

    def _wait_for_clipboard_text(self, previous_text: str) -> str:
        deadline = time.monotonic() + self.config.clipboard_wait_timeout_seconds
        while time.monotonic() < deadline:
            current_text = self._paste_text()
            if current_text != previous_text:
                return current_text
            time.sleep(0.04)
        return self._paste_text()

    def _combo(self, modifier, key: str) -> None:
        self.keyboard.press(modifier)
        try:
            self.keyboard.press(key)
            self.keyboard.release(key)
        finally:
            self.keyboard.release(modifier)

    @staticmethod
    def _paste_text() -> str:
        return _safe_call("", pyperclip.paste)

    @staticmethod
    def _restore_clipboard(text: str) -> None:
        _safe_call(None, pyperclip.copy, text)

    @staticmethod
    def _source_name(control) -> str:
        name = "(unknown focused control)"
        if control is not None:
            name = _safe_call("", lambda: control.Name) or name
        return f"{name} AI chat input"


class SpellEngine:
    def __init__(self, user_words_path: Path = USER_WORDS_FILE, extra_known_words: list[str] | None = None) -> None:
        self.spell = SpellChecker()
        self.user_words_path = user_words_path
        self.spell.word_frequency.load_words(DEFAULT_KNOWN_WORDS)
        if extra_known_words:
            self.spell.word_frequency.load_words(extra_known_words)
        self._load_user_words()

    def find_misspellings(self, text: str) -> list[Misspelling]:
        matches = list(WORD_RE.finditer(text))
        words = [match.group(0) for match in matches]
        unknown = set(self.spell.unknown(words))

        misspellings: list[Misspelling] = []
        for match in matches:
            word = match.group(0)
            if word not in unknown:
                continue
            suggestions = self._suggestions(word)
            misspellings.append(
                Misspelling(
                    word=word,
                    start=match.start(),
                    end=match.end(),
                    suggestions=suggestions,
                )
            )
        return misspellings

    def _suggestions(self, word: str) -> list[str]:
        candidates = self.spell.candidates(word) or set()
        ranked = sorted(candidates, key=lambda item: (item.lower() != word.lower(), len(item), item))
        return ranked[:5]

    def add_word(self, word: str) -> str | None:
        normalized = self._normalize_word(word)
        if not normalized:
            return None

        self.spell.word_frequency.load_words([normalized])
        existing_words = set(self._read_user_words())
        if normalized not in existing_words:
            existing_words.add(normalized)
            self.user_words_path.write_text("\n".join(sorted(existing_words)) + "\n", encoding="utf-8")
        return normalized

    def _load_user_words(self) -> None:
        self.spell.word_frequency.load_words(self._read_user_words())

    def _read_user_words(self) -> list[str]:
        if not self.user_words_path.exists():
            return []
        words = []
        for line in self.user_words_path.read_text(encoding="utf-8").splitlines():
            normalized = self._normalize_word(line)
            if normalized:
                words.append(normalized)
        return words

    @staticmethod
    def _normalize_word(word: str) -> str:
        return word.strip().strip("'").lower()


class Overlay(tk.Tk):
    def __init__(self, on_rescan: Callable[[], None]) -> None:
        super().__init__()
        self.on_rescan = on_rescan
        self.title(APP_TITLE)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.96)
        self.configure(bg="#202124")
        self.withdraw()

        self.container = tk.Frame(self, bg="#202124", padx=12, pady=10)
        self.container.pack(fill="both", expand=True)

        self.status = tk.Label(
            self.container,
            bg="#202124",
            fg="#e8eaed",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left",
        )
        self.status.pack(fill="x")

        self.detail = tk.Label(
            self.container,
            bg="#202124",
            fg="#bdc1c6",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        self.detail.pack(fill="x", pady=(4, 8))

        self.buttons = tk.Frame(self.container, bg="#202124")
        self.buttons.pack(fill="x")

        footer = tk.Frame(self.container, bg="#202124")
        footer.pack(fill="x", pady=(8, 0))

        self.rescan_button = tk.Button(footer, text="Rescan", command=on_rescan)
        self.rescan_button.pack(side="left")

        self.close_button = tk.Button(footer, text="Hide", command=self.withdraw)
        self.close_button.pack(side="right")

    def show_message(self, title: str, detail: str, height: int = 150) -> None:
        self._clear_suggestions()
        self.status.configure(text=title)
        self.detail.configure(text=detail)
        self._place_near_cursor(height=height)
        self.deiconify()
        self.lift()

    def show_misspelling(
        self,
        snapshot: TextSnapshot,
        misspelling: Misspelling,
        on_apply: Callable[[str], None],
        on_ignore: Callable[[], None],
        on_add_word: Callable[[], None],
    ) -> None:
        self._clear_suggestions()
        self.status.configure(text=f"Possible typo: {misspelling.word}")
        detail = f"From {snapshot.source_name}\nRead by {snapshot.extraction_method}"
        if snapshot.replace_note:
            detail = f"{detail}\n{snapshot.replace_note}"
        self.detail.configure(text=detail)

        if not misspelling.suggestions:
            tk.Label(
                self.buttons,
                bg="#202124",
                fg="#bdc1c6",
                text="No suggestions found.",
            ).pack(side="left")
        else:
            for suggestion in misspelling.suggestions:
                button = tk.Button(
                    self.buttons,
                    text=suggestion,
                    command=lambda value=suggestion: on_apply(value),
                    padx=8,
                    pady=3,
                )
                button.pack(side="left", padx=(0, 6))

        tk.Button(self.buttons, text="Ignore", command=on_ignore, padx=8, pady=3).pack(side="left", padx=(8, 6))
        tk.Button(self.buttons, text="Add word", command=on_add_word, padx=8, pady=3).pack(side="left")

        self._place_near_cursor(height=180 if snapshot.replace_note else 150)
        self.deiconify()
        self.lift()

    def _clear_suggestions(self) -> None:
        for child in self.buttons.winfo_children():
            child.destroy()

    def _place_near_cursor(self, width: int = 560, height: int = 150) -> None:
        x, y = _cursor_position()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        left = min(max(16, x + 18), screen_width - width - 16)
        top = min(max(16, y + 18), screen_height - height - 16)
        self.geometry(f"{width}x{height}+{left}+{top}")


class TrayController:
    def __init__(self, app: "SpellOverlayApp") -> None:
        self.app = app
        self.icon = pystray.Icon(
            "AIChatSpellAssistant",
            self._create_icon_image(),
            APP_TITLE,
            pystray.Menu(
                pystray.MenuItem("Scan AI chat input", lambda *_: self.app.scan_active_control()),
                pystray.MenuItem("Scan AI chat with clipboard", lambda *_: self.app.scan_clipboard_fallback()),
                pystray.MenuItem("Diagnostics", lambda *_: self.app.show_diagnostics()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Pause / Resume", lambda *_: self.app.toggle_pause()),
                pystray.MenuItem("Show status", lambda *_: self.app.show_status()),
                pystray.MenuItem("Hide overlay", lambda *_: self.app.hide_overlay()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda *_: self.app.exit_app()),
            ),
        )
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            logging.exception("Failed to stop tray icon")

    @staticmethod
    def _create_icon_image() -> Image.Image:
        image = Image.new("RGBA", (64, 64), (32, 33, 36, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=10, fill=(66, 133, 244, 255))
        draw.text((17, 15), "AI", fill=(255, 255, 255, 255))
        draw.line((20, 46, 44, 46), fill=(255, 255, 255, 255), width=4)
        return image


class SpellOverlayApp:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.target_guard = WindowTargetGuard(self.config)
        self.reader = AccessibilityReader()
        self.clipboard_reader = ClipboardFieldReader(self.config)
        self.engine = SpellEngine(extra_known_words=self.config.extra_known_words)
        self.overlay = Overlay(self.scan_active_control)
        self.last_snapshot: TextSnapshot | None = None
        self.last_misspelling: Misspelling | None = None
        self.listener: keyboard.GlobalHotKeys | None = None
        self.tray = TrayController(self)
        self.paused = False
        self.closing = False

    def run(self) -> None:
        self._start_hotkeys()
        self.tray.start()
        self.overlay.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        if self.config.startup_message:
            self.show_status()
        logging.info("Spell Overlay started")
        self.overlay.mainloop()

    def scan_active_control(self) -> None:
        if self.paused:
            logging.info("Ignored UI Automation scan while paused")
            return
        self.overlay.after(0, self._scan_active_control)

    def scan_clipboard_fallback(self) -> None:
        if self.paused:
            logging.info("Ignored clipboard scan while paused")
            return
        self.overlay.after(180, self._scan_clipboard_fallback)

    def show_diagnostics(self) -> None:
        self.overlay.after(0, self._show_diagnostics)

    def hide_overlay(self) -> None:
        self.overlay.after(0, self.overlay.withdraw)

    def show_status(self) -> None:
        state = "paused" if self.paused else "running"
        self.overlay.after(
            0,
            lambda: self.overlay.show_message(
                f"AI chat spell assistant is {state}",
                (
                    f"{self.config.hotkey_scan} scans the focused AI chat input.\n"
                    f"{self.config.hotkey_clipboard_scan} forces the AI chat clipboard scan.\n"
                    f"{self.config.hotkey_diagnostics} shows target diagnostics. {self.config.hotkey_pause} pauses/resumes."
                ),
                height=205,
            ),
        )

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        logging.info("Pause toggled: %s", self.paused)
        self.show_status()

    def exit_app(self) -> None:
        if self.closing:
            return
        self.closing = True
        logging.info("Spell Overlay exiting")
        if self.listener is not None:
            self.listener.stop()
        self.tray.stop()
        self.overlay.after(0, self.overlay.destroy)

    def _scan_active_control(self) -> None:
        if not self._require_ai_chat_target():
            return

        logging.info("Starting AI chat scan")
        snapshot = None
        if self.config.clipboard_first_for_ai_chat:
            snapshot = self.clipboard_reader.read_focused_field()
        if snapshot is None:
            snapshot = self.reader.read_focused_text()
        self._show_snapshot_results(
            snapshot,
            "No AI chat input text found",
            "Click inside the AI chat input, then scan again.",
        )

    def _scan_clipboard_fallback(self) -> None:
        if not self._require_ai_chat_target():
            return

        logging.info("Starting AI chat clipboard scan")
        snapshot = self.clipboard_reader.read_focused_field()
        self._show_snapshot_results(snapshot, "Clipboard scan found no AI chat text", "Click inside the AI chat input and try again.")

    def _show_snapshot_results(self, snapshot: TextSnapshot | None, empty_title: str, empty_detail: str) -> None:
        if snapshot is None or not snapshot.text.strip():
            logging.info("Scan found no text")
            self.overlay.show_message(empty_title, empty_detail)
            return

        misspellings = self.engine.find_misspellings(snapshot.text)
        logging.info(
            "Scan read %s chars by %s and found %s misspellings",
            len(snapshot.text),
            snapshot.extraction_method,
            len(misspellings),
        )
        if not misspellings:
            self.last_snapshot = snapshot
            self.last_misspelling = None
            self.overlay.show_message(
                "No typos found",
                f"Checked {len(snapshot.text)} characters from {snapshot.source_name}.\nRead by {snapshot.extraction_method}.",
                height=165,
            )
            return

        self.last_snapshot = snapshot
        self.last_misspelling = misspellings[0]
        self._show_current_misspelling()

    def _show_diagnostics(self) -> None:
        diagnostics = f"{self.target_guard.describe_active_target()}\n\n{self.reader.describe_focused_control()}"
        logging.info("Focused control diagnostics:\n%s", diagnostics)
        self.overlay.show_message(
            "AI chat target diagnostics",
            diagnostics,
            height=330,
        )

    def _require_ai_chat_target(self) -> bool:
        match = self.target_guard.match_active_target()
        logging.info("AI chat target check: %s (%s)", match.allowed, match.reason)
        if match.allowed:
            return True

        detail = (
            "Nothing was scanned because this app is limited to AI agent chat inputs.\n"
            f"Reason: {match.reason}\n"
            f"Window: {match.info.title or '(empty)'}\n"
            f"Process: {match.info.process_name or '(unknown)'}\n"
            "Focus Codex, Antigravity, ChatGPT, or add a target keyword in settings.json."
        )
        self.overlay.show_message("AI chat target not detected", detail, height=240)
        return False

    def apply_suggestion(self, suggestion: str) -> None:
        snapshot = self.last_snapshot
        misspelling = self.last_misspelling
        if snapshot is None or misspelling is None:
            return

        updated_text = (
            snapshot.text[: misspelling.start]
            + self._preserve_case(misspelling.word, suggestion)
            + snapshot.text[misspelling.end :]
        )

        if snapshot.setter and snapshot.setter(updated_text):
            updated_snapshot = TextSnapshot(
                updated_text,
                snapshot.source_name,
                snapshot.setter,
                snapshot.extraction_method,
                snapshot.replace_note,
            )
            self.last_snapshot = updated_snapshot
            next_misspelling = self._next_misspelling(updated_text, misspelling.start)
            if next_misspelling:
                self.last_misspelling = next_misspelling
                self._show_current_misspelling()
                return

            self.overlay.show_message("Correction applied", f"Replaced {misspelling.word} with {suggestion}.")
            return

        pyperclip.copy(suggestion)
        self.overlay.show_message(
            "Suggestion copied",
            "This control is read-only through UI Automation, so the correction was copied to the clipboard.",
        )

    def ignore_current(self) -> None:
        snapshot = self.last_snapshot
        misspelling = self.last_misspelling
        if snapshot is None or misspelling is None:
            return
        self._advance_after(snapshot, misspelling.end, "Ignored current typo")

    def add_current_word(self) -> None:
        snapshot = self.last_snapshot
        misspelling = self.last_misspelling
        if snapshot is None or misspelling is None:
            return
        added_word = self.engine.add_word(misspelling.word)
        if added_word is None:
            return
        self._advance_after(snapshot, misspelling.start, f"Added {added_word} to user_words.txt")

    def _advance_after(self, snapshot: TextSnapshot, index: int, done_title: str) -> None:
        next_misspelling = self._next_misspelling(snapshot.text, index, wrap=False)
        if next_misspelling:
            self.last_misspelling = next_misspelling
            self._show_current_misspelling()
            return

        self.last_misspelling = None
        self.overlay.show_message(done_title, "No more typos found in the current text.")

    def _show_current_misspelling(self) -> None:
        if self.last_snapshot is None or self.last_misspelling is None:
            return
        self.overlay.show_misspelling(
            self.last_snapshot,
            self.last_misspelling,
            self.apply_suggestion,
            self.ignore_current,
            self.add_current_word,
        )

    def _start_hotkeys(self) -> None:
        self.listener = keyboard.GlobalHotKeys(
            {
                self.config.hotkey_scan: self.scan_active_control,
                self.config.hotkey_clipboard_scan: self.scan_clipboard_fallback,
                self.config.hotkey_diagnostics: self.show_diagnostics,
                self.config.hotkey_pause: self.toggle_pause,
                self.config.hotkey_hide: self.hide_overlay,
            }
        )
        thread = threading.Thread(target=self.listener.run, daemon=True)
        thread.start()

    @staticmethod
    def _preserve_case(original: str, suggestion: str) -> str:
        if original.isupper():
            return suggestion.upper()
        if original[:1].isupper():
            return suggestion.capitalize()
        return suggestion

    def _next_misspelling(self, text: str, after_index: int, wrap: bool = True) -> Misspelling | None:
        misspellings = self.engine.find_misspellings(text)
        for misspelling in misspellings:
            if misspelling.start >= after_index:
                return misspelling
        return misspellings[0] if wrap and misspellings else None


if __name__ == "__main__":
    configure_logging()
    SpellOverlayApp().run()
