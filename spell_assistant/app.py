from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

import pyperclip

from spell_assistant.config import AppConfig
from spell_assistant.models import ActiveWindowInfo, Misspelling, TextSnapshot
from spell_assistant.window_guard import WindowTargetGuard, AccessibilityReader
from spell_assistant.clipboard import SelectionEditor
from spell_assistant.engine import SpellEngine
from spell_assistant.ui import MainWindow, TrayController
from spell_assistant.hotkeys import NativeHotKeyListener
from spell_assistant.utils import set_app_user_model_id


class AIAgentChatSpellAssistantApp:
    def __init__(self) -> None:
        set_app_user_model_id()
        self.config = AppConfig.load()
        # We don't strictly need WindowTargetGuard anymore since we removed the restriction, but leaving it initialized is fine
        self.target_guard = WindowTargetGuard(self.config)
        self.reader = AccessibilityReader()
        self.selection_editor = SelectionEditor(self.config)
        self.engine = SpellEngine(extra_known_words=self.config.extra_known_words)
        
        self.main_window = MainWindow(self._editor_apply, self._editor_copy, self._editor_add_word, self.engine.find_misspellings)
        self.tray = TrayController(self)
        
        self.listener: NativeHotKeyListener | None = None
        self.closing = False
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.current_snapshot: TextSnapshot | None = None

    def run(self) -> None:
        self._start_hotkeys()
        self.tray.start()
        self.main_window.after(50, self._drain_ui_queue)
        
        # Open it immediately on startup
        self.main_window.show_text("Ready. Highlight text anywhere and press Alt+Q.", [])
        
        logging.info("Spell Assistant started (Persistent Window Mode)")
        self.main_window.mainloop()

    def scan_selected_text(self) -> None:
        logging.info("Hotkey pressed. Queuing check selection.")
        self._run_on_ui(lambda: self.main_window.after(100, self._check_selection))
        
    def quick_fix_selected_text(self) -> None:
        logging.info("Quick fix hotkey pressed. Applying top suggestions instantly.")
        self._run_on_ui(lambda: self._quick_fix_process())

    def _quick_fix_process(self) -> None:
        snapshot = self.selection_editor.read_selected_text()
        if snapshot is None or not snapshot.text.strip():
            return
            
        misspellings = self.engine.find_misspellings(snapshot.text)
        if not misspellings:
            return
            
        # Apply top suggestion to all misspellings starting from the end to preserve indices
        text = snapshot.text
        for m in reversed(misspellings):
            if m.suggestions:
                suggestion = m.suggestions[0]
                original = text[m.start:m.end]
                if original.isupper():
                    suggestion = suggestion.upper()
                elif original[:1].isupper():
                    suggestion = suggestion.capitalize()
                text = text[:m.start] + suggestion + text[m.end:]
                
        if snapshot.setter:
            snapshot.setter(text, None, None)
            self.engine.learn_from_text(text)
            logging.info("Quick fix applied instantly.")

    def _check_selection(self) -> None:
        logging.info("Checking selected text via clipboard")
        snapshot = self.selection_editor.read_selected_text()
        
        if snapshot is None or not snapshot.text.strip():
            logging.info("Scan found no text")
            self.main_window.show_text("No text selected. Highlight text and press Alt+Q.", [])
            return

        self.current_snapshot = snapshot
        misspellings = self.engine.find_misspellings(snapshot.text)
        logging.info(
            "Scan read %s chars and found %s misspellings",
            len(snapshot.text),
            len(misspellings),
        )
        
        self.main_window.show_text(snapshot.text, misspellings)

    def show_editor(self) -> None:
        self._run_on_ui(lambda: self.main_window.deiconify() or self.main_window.lift() or self.main_window.focus_force())

    def exit_app(self) -> None:
        if self.closing:
            return
        self.closing = True
        logging.info("Exiting")
        if self.listener is not None:
            self.listener.stop()
        self.tray.stop()
        self._run_on_ui(self.main_window.destroy)

    def _run_on_ui(self, action: Callable[[], None]) -> None:
        self.ui_queue.put(action)

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                action = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except Exception:
                logging.exception("UI action failed")
        if not self.closing:
            self.main_window.after(50, self._drain_ui_queue)

    def _editor_apply(self, suggestion: str, typo_idx: int) -> None:
        logging.info("Applied suggestion %s for typo %s", suggestion, typo_idx)

    def _editor_copy(self, final_text: str) -> None:
        pyperclip.copy(final_text)
        self.engine.learn_from_text(final_text)
        logging.info("Copied corrected text to clipboard and learned bigrams")
        
        # Auto-paste feature!
        if self.current_snapshot and self.current_snapshot.setter:
            self.current_snapshot.setter(final_text, None, None)
            logging.info("Auto-pasted corrected text back to target application")

    def _editor_add_word(self, word: str) -> None:
        normalized = self.engine.add_word(word)
        if normalized:
            logging.info("Added word to dictionary: %s", normalized)

    def _start_hotkeys(self) -> None:
        self.listener = NativeHotKeyListener(
            {
                self.config.hotkey_scan: self.scan_selected_text,
                self.config.hotkey_quick_fix: self.quick_fix_selected_text,
                self.config.hotkey_diagnostics: lambda: None, # diagnostics removed for simplicity
                self.config.hotkey_pause: lambda: None, # pause removed for simplicity
            }
        )
        self.listener.start()
