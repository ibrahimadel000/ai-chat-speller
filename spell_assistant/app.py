from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

import pyperclip

from spell_assistant.config import AppConfig
from spell_assistant.models import ActiveWindowInfo, Misspelling, TextSnapshot
from spell_assistant.window_guard import WindowTargetGuard, AccessibilityReader
from spell_assistant.clipboard import SurgicalFieldEditor
from spell_assistant.engine import SpellEngine
from spell_assistant.ui import Overlay, TrayController, SettingsWindow, FloatingBadge
from spell_assistant.hotkeys import NativeHotKeyListener


class AIAgentChatSpellAssistantApp:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.target_guard = WindowTargetGuard(self.config)
        self.reader = AccessibilityReader()
        self.clipboard_reader = SurgicalFieldEditor(self.config)
        self.engine = SpellEngine(extra_known_words=self.config.extra_known_words)
        self.overlay = Overlay(self.scan_active_control)
        self.floating_badge = FloatingBadge(self.apply_suggestion, self.scan_active_control)
        self.last_snapshot: TextSnapshot | None = None
        self.last_misspelling: Misspelling | None = None
        self.current_misspellings: list[Misspelling] = []
        self.current_index = 0
        self.listener: NativeHotKeyListener | None = None
        self.tray = TrayController(self)
        self.paused = False
        self.closing = False
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.pending_target_info: ActiveWindowInfo | None = None

    def run(self) -> None:
        self._start_hotkeys()
        self.tray.start()
        threading.Thread(target=self._passive_scan_loop, daemon=True).start()
        self.overlay.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        self.overlay.after(50, self._drain_ui_queue)
        if self.config.startup_message:
            self.show_status()
            self.overlay.after(700, self._show_hotkey_registration_status)
        logging.info("AI Agent Chat Spell Assistant started")
        self.overlay.mainloop()

    def _passive_scan_loop(self) -> None:
        while True:
            time.sleep(2.0)
            if self.paused or self.closing:
                self._run_on_ui(self.floating_badge.hide)
                continue
            
            try:
                match = self.target_guard.match_active_target()
                if not match.allowed:
                    self._run_on_ui(self.floating_badge.hide)
                    continue
                
                snapshot = self.clipboard_reader.read_focused_field(silent_only=True)
                if not snapshot or not snapshot.text.strip():
                    self._run_on_ui(self.floating_badge.hide)
                    continue

                misspellings = self.engine.find_misspellings(snapshot.text)
                if misspellings:
                    self.last_snapshot = snapshot
                    self.last_misspelling = misspellings[0]
                    self.current_misspellings = misspellings
                    self.current_index = 0
                    self._run_on_ui(lambda m=misspellings[0]: self.floating_badge.show(m))
                else:
                    self._run_on_ui(self.floating_badge.hide)
            except Exception as e:
                logging.error(f"Passive scan error: {e}")

    def scan_active_control(self) -> None:
        if self.paused:
            logging.info("Ignored AI agent chat scan while paused")
            return
        self._run_on_ui(lambda: self.overlay.after(180, self._scan_active_control))

    def show_diagnostics(self) -> None:
        self._run_on_ui(self._show_diagnostics)

    def trust_current_window(self) -> None:
        self._run_on_ui(self._trust_current_window)

    def open_settings(self) -> None:
        self._run_on_ui(self._show_settings_window)

    def hide_overlay(self) -> None:
        self._run_on_ui(self.overlay.withdraw)

    def show_status(self) -> None:
        state = "paused" if self.paused else "running"
        self._run_on_ui(
            lambda: self.overlay.show_message(
                f"AI agent chat assistant is {state}",
                (
                    f"{self.config.hotkey_scan} scans only the focused AI agent chat input.\n"
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
        logging.info("AI Agent Chat Spell Assistant exiting")
        if self.listener is not None:
            self.listener.stop()
        self.tray.stop()
        self._run_on_ui(self.overlay.destroy)

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
            self.overlay.after(50, self._drain_ui_queue)

    def _scan_active_control(self) -> None:
        if not self._require_ai_chat_target():
            return

        logging.info("Starting AI agent chat clipboard scan")
        snapshot = self.clipboard_reader.read_focused_field()
        self._show_snapshot_results(
            snapshot,
            "No AI agent chat input text found",
            "Click inside the AI agent chat input, then scan again.",
        )

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
            self.current_misspellings = []
            self.current_index = 0
            self.overlay.show_message(
                "No typos found",
                f"Checked {len(snapshot.text)} characters from {snapshot.source_name}.\nRead by {snapshot.extraction_method}.",
                height=165,
            )
            return

        self.last_snapshot = snapshot
        self.current_misspellings = misspellings
        self.current_index = 0
        self.last_misspelling = self.current_misspellings[self.current_index]
        self._show_current_misspelling()

    def _show_diagnostics(self) -> None:
        diagnostics = f"{self.target_guard.describe_active_target()}\n\n{self.reader.describe_focused_control()}"
        logging.info("Focused control diagnostics:\n%s", diagnostics)
        self.overlay.show_message(
            "AI agent chat target diagnostics",
            diagnostics,
            height=330,
        )

    def _show_settings_window(self) -> None:
        SettingsWindow(self.config)

    def _trust_current_window(self) -> None:
        info = self.target_guard.active_window_info()
        self._trust_target_info(info)

    def _trust_pending_target(self) -> None:
        if self.pending_target_info is None:
            self.overlay.show_message("No AI agent window pending", "Try scanning again while focused in the AI agent chat input.")
            return
        self._trust_target_info(self.pending_target_info)

    def _trust_target_info(self, info: ActiveWindowInfo) -> None:
        if not info.title.strip() and not info.process_path.strip():
            self.overlay.show_message("Could not trust current window", "No active window title or process path was detected.")
            return

        added_items = []
        if info.title.strip() and info.title not in self.config.trusted_window_title_keywords:
            self.config.trusted_window_title_keywords.append(info.title)
            added_items.append(f"title: {info.title}")
        if info.process_path.strip() and info.process_path not in self.config.trusted_process_paths:
            self.config.trusted_process_paths.append(info.process_path)
            added_items.append(f"path: {info.process_path}")
        self.config.save()
        logging.info("Trusted current AI agent window: %s", added_items)
        if added_items:
            detail = "Added this AI agent window to settings.json:\n" + "\n".join(added_items)
        else:
            detail = "This AI agent window was already trusted."
        self.overlay.show_message("AI agent window trusted", detail, height=230)

    def _require_ai_chat_target(self) -> bool:
        match = self.target_guard.match_active_target()
        logging.info("AI agent chat target check: %s (%s)", match.allowed, match.reason)
        if match.allowed:
            return True

        detail = (
            "Nothing was scanned because this app only works inside AI agent chat inputs.\n"
            f"Reason: {match.reason}\n"
            f"Window: {match.info.title or '(empty)'}\n"
            f"Process: {match.info.process_name or '(unknown)'}\n"
            "Use the tray action 'Trust current AI agent window' while focused in Codex/Antigravity if this is the right chat."
        )
        self.pending_target_info = match.info
        self.overlay.show_message(
            "AI agent chat target not detected",
            detail,
            height=260,
            actions=[
                ("Trust this AI agent window", self._trust_pending_target, "primary"),
                ("Diagnostics", self._show_diagnostics, "secondary"),
            ],
        )
        return False

    def apply_suggestion(self, suggestion: str, from_badge: bool = False) -> None:
        snapshot = self.last_snapshot
        misspelling = self.last_misspelling
        if snapshot is None or misspelling is None:
            return

        preserved_suggestion = self._preserve_case(misspelling.word, suggestion)
        updated_text = (
            snapshot.text[: misspelling.start]
            + preserved_suggestion
            + snapshot.text[misspelling.end :]
        )

        if snapshot.setter and snapshot.setter(preserved_suggestion, len(snapshot.text), misspelling.start, misspelling.end):
            updated_snapshot = TextSnapshot(
                updated_text,
                snapshot.source_name,
                snapshot.setter,
                snapshot.extraction_method,
                snapshot.replace_note,
            )
            self.last_snapshot = updated_snapshot
            if self._select_next_misspelling(updated_text, misspelling.start, wrap=True):
                if not from_badge:
                    self._show_current_misspelling()
                return

            self.last_misspelling = None
            if not from_badge:
                self.overlay.show_message("Correction applied", f"Replaced {misspelling.word} with {suggestion}.")
            return

        pyperclip.copy(suggestion)
        if not from_badge:
            self.overlay.show_message(
                "Suggestion copied",
                "The AI agent chat input could not be rewritten, so the correction was copied to the clipboard.",
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
        if self._select_next_misspelling(snapshot.text, index, wrap=False):
            self._show_current_misspelling()
            return

        self.last_misspelling = None
        self.current_misspellings = []
        self.current_index = 0
        self.overlay.show_message(done_title, "No more typos found in the current text.")

    def _show_current_misspelling(self) -> None:
        if self.last_snapshot is None or self.last_misspelling is None:
            return
        self.overlay.show_misspelling(
            self.last_snapshot,
            self.last_misspelling,
            self.current_index,
            len(self.current_misspellings),
            self.apply_suggestion,
            self.ignore_current,
            self.add_current_word,
        )

    def _start_hotkeys(self) -> None:
        self.listener = NativeHotKeyListener(
            {
                self.config.hotkey_scan: self.scan_active_control,
                self.config.hotkey_diagnostics: self.show_diagnostics,
                self.config.hotkey_pause: self.toggle_pause,
            }
        )
        self.listener.start()

    def _show_hotkey_registration_status(self) -> None:
        if self.listener and self.listener.failed_hotkeys:
            detail = (
                "These hotkeys could not be registered, probably because another app already owns them:\n"
                + ", ".join(self.listener.failed_hotkeys)
                + "\nChange them in settings.json or use the tray menu."
            )
            self.overlay.show_message("Hotkey registration problem", detail, height=220)

    @staticmethod
    def _preserve_case(original: str, suggestion: str) -> str:
        if original.isupper():
            return suggestion.upper()
        if original[:1].isupper():
            return suggestion.capitalize()
        return suggestion

    def _select_next_misspelling(self, text: str, after_index: int, wrap: bool = True) -> bool:
        self.current_misspellings = self.engine.find_misspellings(text)
        for index, misspelling in enumerate(self.current_misspellings):
            if misspelling.start >= after_index:
                self.current_index = index
                self.last_misspelling = misspelling
                return True
        if wrap and self.current_misspellings:
            self.current_index = 0
            self.last_misspelling = self.current_misspellings[0]
            return True
        return False
