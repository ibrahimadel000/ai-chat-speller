from __future__ import annotations

import logging
import time
from typing import Callable

import pyperclip
import uiautomation as auto
from pynput import keyboard

from spell_assistant.config import AppConfig
from spell_assistant.models import TextSnapshot
from spell_assistant.utils import _safe_call


class SurgicalFieldEditor:
    """Reads and rewrites only the focused AI agent chat input via clipboard shortcuts."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.keyboard = keyboard.Controller()

    def _is_valid_text(self, text: str | None, marker: str | None = None) -> bool:
        if not text or (marker and text == marker) or not text.strip():
            return False
        if len(text) > self.config.max_chat_input_chars:
            logging.warning("Rejected text with %s chars; likely not a chat input", len(text))
            return False
        return True

    def read_focused_field(self, silent_only: bool = False) -> TextSnapshot | None:
        control = _safe_call(None, auto.GetFocusedControl)
        source_name = self._source_name(control)

        if control is not None:
            value_pattern = _safe_call(None, control.GetValuePattern)
            if value_pattern is not None:
                text = _safe_call("", lambda: value_pattern.Value)
                if self._is_valid_text(text):
                    return TextSnapshot(
                        text,
                        source_name,
                        self._field_replacer(control),
                        "UI Automation ValuePattern",
                        "Replacement uses surgical keyboard macro.",
                    )

            text_pattern = _safe_call(None, control.GetTextPattern)
            if text_pattern is not None:
                text = _safe_call("", lambda: text_pattern.DocumentRange.GetText(-1))
                if self._is_valid_text(text):
                    return TextSnapshot(
                        text,
                        source_name,
                        self._field_replacer(control),
                        "UI Automation TextPattern",
                        "Replacement uses surgical keyboard macro.",
                    )

        if silent_only:
            return None

        previous_clipboard = self._paste_text()
        marker = f"__SPELL_OVERLAY_MARKER_{time.monotonic_ns()}__"

        try:
            if control is not None:
                _safe_call(None, control.SetFocus)
                time.sleep(self.config.clipboard_focus_delay_seconds)
            if not self._copy_text(marker):
                return None
            copied_text = self._wait_for_clipboard_text(marker)
        finally:
            self._restore_clipboard(previous_clipboard)

        if not self._is_valid_text(copied_text, marker):
            return None

        return TextSnapshot(
            copied_text,
            source_name,
            self._field_replacer(control),
            "clipboard fallback",
            "Replacement uses surgical keyboard macro.",
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

    def _field_replacer(self, control) -> Callable[[str, int, int, int], bool]:
        def replace_text(new_text: str, original_length: int, start_idx: int, end_idx: int) -> bool:
            try:
                if control is None:
                    return False
                control.SetFocus()
                time.sleep(self.config.clipboard_focus_delay_seconds)

                # 2. Send Ctrl+End to jump to the end of the text.
                self._combo(keyboard.Key.ctrl, keyboard.Key.end)
                time.sleep(0.05)

                # 3. Send Left arrow `original_length - end_idx` times.
                left_moves = original_length - end_idx
                for _ in range(left_moves):
                    self._tap(keyboard.Key.left)
                time.sleep(0.05)

                # 4. Send Shift+Left arrow `end_idx - start_idx` times to highlight the word.
                shift_left_moves = end_idx - start_idx
                self.keyboard.press(keyboard.Key.shift)
                try:
                    for _ in range(shift_left_moves):
                        self._tap(keyboard.Key.left)
                finally:
                    self.keyboard.release(keyboard.Key.shift)
                time.sleep(0.05)

                # 5. Use keyboard.type(new_text) or copy/paste it to replace.
                previous_clipboard = self._paste_text()
                try:
                    pyperclip.copy(new_text)
                    time.sleep(self.config.clipboard_paste_delay_seconds)
                    self._combo(keyboard.Key.ctrl, "v")
                    time.sleep(0.12)
                finally:
                    self._restore_clipboard(previous_clipboard)

                # 6. Send Ctrl+End to return the caret to the end.
                self._combo(keyboard.Key.ctrl, keyboard.Key.end)

                return True
            except Exception as e:
                logging.error(f"Surgical replacement failed: {e}")
                return False

        return replace_text

    def _wait_for_clipboard_text(self, previous_text: str) -> str:
        deadline = time.monotonic() + self.config.clipboard_wait_timeout_seconds
        while time.monotonic() < deadline:
            current_text = self._paste_text()
            if current_text != previous_text:
                return current_text
            time.sleep(0.04)
        return self._paste_text()

    def _tap(self, key) -> None:
        self.keyboard.press(key)
        self.keyboard.release(key)

    def _combo(self, modifier, key) -> None:
        self.keyboard.press(modifier)
        try:
            self._tap(key)
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
        return f"{name} AI agent chat input"
