from __future__ import annotations

import logging
import time

import pyperclip
from pynput import keyboard

from spell_assistant.config import AppConfig
from spell_assistant.models import TextSnapshot, Misspelling
from spell_assistant.utils import _safe_call


class SelectionEditor:
    """Manual field editor that copies highlighted text via Ctrl+C, checks it, and pastes fixes via Ctrl+V."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.keyboard = keyboard.Controller()

    def read_selected_text(self) -> TextSnapshot | None:
        previous_clipboard = _safe_call("", pyperclip.paste)
        marker = f"__SPELL_OVERLAY_MARKER_{time.monotonic_ns()}__"
        _safe_call(None, pyperclip.copy, marker)

        # Release modifiers that might still be physically held down from the hotkey press
        self.keyboard.release(keyboard.Key.alt)
        self.keyboard.release(keyboard.Key.ctrl)
        self.keyboard.release(keyboard.Key.shift)
        time.sleep(0.05)

        # Send Ctrl+C to copy the currently highlighted text
        self._combo(keyboard.Key.ctrl, "c")

        # Wait for clipboard to change (much faster polling)
        copied_text = ""
        deadline = time.monotonic() + 0.3 # Reduced from 1.2s
        while time.monotonic() < deadline:
            current = _safe_call("", pyperclip.paste)
            if current != marker:
                copied_text = current
                break
            time.sleep(0.01) # Reduced from 0.04s

        # Restore original clipboard
        _safe_call(None, pyperclip.copy, previous_clipboard)

        if not copied_text or not copied_text.strip():
            return None

        if len(copied_text) > self.config.max_chat_input_chars:
            logging.warning(f"Rejected highlighted text with {len(copied_text)} chars; too large.")
            return None

        return TextSnapshot(
            text=copied_text,
            source_name="Selected Text",
            setter=self._replace_selected_text,
            extraction_method="Ctrl+C (Manual Selection)",
            replace_note="Correction will be pasted directly over the highlighted selection.",
        )

    def _replace_selected_text(self, updated_full_text: str, misspelling: Misspelling, suggestion: str) -> bool:
        """Pastes the corrected text completely replacing the current active highlight."""
        previous_clipboard = _safe_call("", pyperclip.paste)
        try:
            # The text is still highlighted by the user. Just copy the updated string and Ctrl+V
            pyperclip.copy(updated_full_text)
            time.sleep(0.02) # Drastically reduced from config paste delay
            self._combo(keyboard.Key.ctrl, "v")
            time.sleep(0.02)
            return True
        except Exception as e:
            logging.error(f"Selection replacement failed: {e}")
            return False
        finally:
            self._restore_clipboard(previous_clipboard)

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
    def _restore_clipboard(text: str) -> None:
        _safe_call(None, pyperclip.copy, text)
