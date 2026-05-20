from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Callable, TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from spell_assistant.config import APP_TITLE
from spell_assistant.models import Misspelling, TextSnapshot
from spell_assistant.utils import _cursor_position

if TYPE_CHECKING:
    from spell_assistant.app import AIAgentChatSpellAssistantApp

class Overlay(tk.Tk):
    BG = "#111315"
    PANEL = "#181b20"
    TEXT = "#f2f4f8"
    MUTED = "#a8b0bd"
    ACCENT = "#4f8cff"
    BAD = "#ff5c7a"
    BAD_BG = "#3a1822"
    GOOD = "#28c081"
    BORDER = "#2a2f38"

    def __init__(self, on_rescan: Callable[[], None]) -> None:
        super().__init__()
        self.on_rescan = on_rescan
        self.suggestion_actions: list[Callable[[], None]] = []
        self.title(APP_TITLE)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.98)
        self.configure(bg=self.BORDER)
        self.withdraw()
        self.bind("<Escape>", lambda _event: self.withdraw())
        self.bind("<Return>", lambda _event: self._apply_suggestion_by_index(0))
        for index in range(1, 6):
            self.bind(str(index), lambda _event, value=index: self._apply_suggestion_by_index(value - 1))

        self.container = tk.Frame(self, bg=self.BG, padx=14, pady=12)
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Frame(self.container, bg=self.BG)
        header.pack(fill="x")

        self.status = tk.Label(
            header,
            bg=self.BG,
            fg=self.TEXT,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            justify="left",
        )
        self.status.pack(side="left", fill="x", expand=True)

        self.progress = tk.Label(
            header,
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            anchor="e",
        )
        self.progress.pack(side="right")

        self.detail = tk.Label(
            self.container,
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=590,
        )
        self.detail.pack(fill="x", pady=(5, 10))

        self.word_row = tk.Frame(self.container, bg=self.BG)
        tk.Label(
            self.word_row,
            text="Wrong word",
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left")
        self.word_badge = tk.Label(
            self.word_row,
            bg=self.BAD_BG,
            fg=self.BAD,
            font=("Segoe UI", 12, "bold"),
            padx=10,
            pady=4,
        )
        self.word_badge.pack(side="left", padx=(8, 0))

        self.context = tk.Text(
            self.container,
            height=3,
            wrap="word",
            bg=self.PANEL,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground=self.ACCENT,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
            cursor="arrow",
        )
        self.context.tag_configure("bad", foreground="#ffffff", background=self.BAD, font=("Segoe UI", 9, "bold"))
        self.context.tag_configure("muted", foreground=self.MUTED)
        self.context.configure(state="disabled")

        self.buttons = tk.Frame(self.container, bg=self.BG)
        self.buttons.pack(fill="x", pady=(10, 0))

        footer = tk.Frame(self.container, bg=self.BG)
        footer.pack(fill="x", pady=(12, 0))

        self.hint = tk.Label(
            footer,
            text="Enter applies first suggestion. 1-5 applies a numbered suggestion.",
            bg=self.BG,
            fg=self.MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.hint.pack(side="left", fill="x", expand=True)

        self.rescan_button = self._button(footer, "Rescan", on_rescan, "secondary")
        self.rescan_button.pack(side="left", padx=(8, 6))

        self.close_button = self._button(footer, "Hide", self.withdraw, "secondary")
        self.close_button.pack(side="left")

    def show_message(
        self,
        title: str,
        detail: str,
        height: int = 170,
        actions: list[tuple[str, Callable[[], None], str]] | None = None,
    ) -> None:
        self._clear_suggestions()
        self._hide_detection_widgets()
        self.status.configure(text=title)
        self.progress.configure(text="")
        self.detail.configure(text=detail)
        self.hint.configure(text="Ctrl+Alt+S scans the focused AI agent chat input.")
        if actions:
            for label, command, variant in actions:
                self._button(self.buttons, label, command, variant).pack(side="left", padx=(0, 7), pady=(0, 4))
        self._place_near_cursor(height=height)
        self.deiconify()
        self.lift()
        self.focus_force()

    def show_misspelling(
        self,
        snapshot: TextSnapshot,
        misspelling: Misspelling,
        current_index: int,
        total_count: int,
        on_apply: Callable[[str], None],
        on_ignore: Callable[[], None],
        on_add_word: Callable[[], None],
    ) -> None:
        self._clear_suggestions()
        self._show_detection_widgets()
        self.status.configure(text="Wrong word detected")
        self.progress.configure(text=f"Typo {current_index + 1} of {total_count}")
        self.word_badge.configure(text=misspelling.word)
        detail = f"{snapshot.source_name} - {snapshot.extraction_method}"
        if snapshot.replace_note:
            detail = f"{detail}\n{snapshot.replace_note}"
        self.detail.configure(text=detail)
        self._set_context(misspelling)

        if not misspelling.suggestions:
            tk.Label(
                self.buttons,
                bg=self.BG,
                fg=self.MUTED,
                text="No suggestions found.",
                font=("Segoe UI", 9),
            ).pack(side="left")
        else:
            for index, suggestion in enumerate(misspelling.suggestions, start=1):
                action = lambda value=suggestion: on_apply(value)
                self.suggestion_actions.append(action)
                button = self._button(self.buttons, f"{index}. {suggestion}", action, "primary")
                button.pack(side="left", padx=(0, 7), pady=(0, 4))

        self._button(self.buttons, "Ignore", on_ignore, "secondary").pack(side="left", padx=(8, 7), pady=(0, 4))
        self._button(self.buttons, "Add word", on_add_word, "secondary").pack(side="left", pady=(0, 4))
        self.hint.configure(text="Enter applies first suggestion. Number keys 1-5 apply suggestions.")

        self._place_near_cursor(height=285)
        self.deiconify()
        self.lift()
        self.focus_force()

    def _set_context(self, misspelling: Misspelling) -> None:
        self.context.configure(state="normal")
        self.context.delete("1.0", "end")
        if misspelling.context_before:
            self.context.insert("end", f"... {misspelling.context_before} ", "muted")
        self.context.insert("end", misspelling.word, "bad")
        if misspelling.context_after:
            self.context.insert("end", f" {misspelling.context_after} ...", "muted")
        self.context.configure(state="disabled")

    def _show_detection_widgets(self) -> None:
        if not self.word_row.winfo_ismapped():
            self.word_row.pack(fill="x", pady=(0, 8))
        if not self.context.winfo_ismapped():
            self.context.pack(fill="x")

    def _hide_detection_widgets(self) -> None:
        self.word_row.pack_forget()
        self.context.pack_forget()

    def _clear_suggestions(self) -> None:
        self.suggestion_actions = []
        for child in self.buttons.winfo_children():
            child.destroy()

    def _apply_suggestion_by_index(self, index: int) -> None:
        if 0 <= index < len(self.suggestion_actions):
            self.suggestion_actions[index]()

    def _button(self, parent, text: str, command: Callable[[], None], variant: str) -> tk.Button:
        if variant == "primary":
            bg, fg, active_bg = self.ACCENT, "#ffffff", "#6fa2ff"
        else:
            bg, fg, active_bg = self.PANEL, self.TEXT, "#242932"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            font=("Segoe UI", 9, "bold" if variant == "primary" else "normal"),
            cursor="hand2",
        )

    def _place_near_cursor(self, width: int = 640, height: int = 170) -> None:
        x, y = _cursor_position()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        left = min(max(16, x + 18), screen_width - width - 16)
        top = min(max(16, y + 18), screen_height - height - 16)
        self.geometry(f"{width}x{height}+{left}+{top}")

class SettingsWindow(tk.Toplevel):
    BG = "#111315"
    PANEL = "#181b20"
    TEXT = "#f2f4f8"
    MUTED = "#a8b0bd"
    ACCENT = "#4f8cff"
    BAD = "#ff5c7a"
    BAD_BG = "#3a1822"
    GOOD = "#28c081"
    BORDER = "#2a2f38"

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.title("Settings")
        self.configure(bg=self.BG)
        self.geometry("600x500")

        self.container = tk.Frame(self, bg=self.BG, padx=14, pady=12)
        self.container.pack(fill="both", expand=True)

        self.lists: dict[str, tk.Listbox] = {}

        self._create_section("Target Keywords", "target_keywords")
        self._create_section("Trusted Window Title Keywords", "trusted_window_title_keywords")
        self._create_section("Trusted Process Paths", "trusted_process_paths")

        footer = tk.Frame(self.container, bg=self.BG)
        footer.pack(fill="x", pady=(12, 0))

        save_btn = tk.Button(
            footer, text="Save", command=self.save_and_close,
            bg=self.ACCENT, fg="#ffffff", activebackground="#6fa2ff", activeforeground="#ffffff",
            relief="flat", bd=0, padx=10, pady=5, font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        save_btn.pack(side="right")

    def _create_section(self, label: str, config_key: str) -> None:
        frame = tk.Frame(self.container, bg=self.BG)
        frame.pack(fill="x", pady=(0, 10))

        tk.Label(frame, text=label, bg=self.BG, fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        listbox = tk.Listbox(frame, bg=self.PANEL, fg=self.TEXT, selectbackground=self.ACCENT, relief="flat", bd=0, height=4)
        listbox.pack(fill="x", pady=(4, 4))

        items = getattr(self.config, config_key)
        for item in items:
            listbox.insert("end", item)

        self.lists[config_key] = listbox

        btn_frame = tk.Frame(frame, bg=self.BG)
        btn_frame.pack(fill="x")

        entry = tk.Entry(btn_frame, bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", bd=0)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def add_item() -> None:
            val = entry.get().strip()
            if val:
                listbox.insert("end", val)
                entry.delete(0, "end")

        def remove_item() -> None:
            selection = listbox.curselection()
            if selection:
                listbox.delete(selection[0])

        add_btn = tk.Button(
            btn_frame, text="Add", command=add_item,
            bg=self.PANEL, fg=self.TEXT, activebackground="#242932", activeforeground=self.TEXT,
            relief="flat", bd=0, padx=8, font=("Segoe UI", 9), cursor="hand2"
        )
        add_btn.pack(side="left", padx=(0, 5))

        remove_btn = tk.Button(
            btn_frame, text="Remove Selected", command=remove_item,
            bg=self.PANEL, fg=self.TEXT, activebackground="#242932", activeforeground=self.TEXT,
            relief="flat", bd=0, padx=8, font=("Segoe UI", 9), cursor="hand2"
        )
        remove_btn.pack(side="left")

    def save_and_close(self) -> None:
        for key, listbox in self.lists.items():
            setattr(self.config, key, list(listbox.get(0, "end")))
        self.config.save()
        self.destroy()

class SettingsWindow(tk.Toplevel):
    BG = "#111315"
    PANEL = "#181b20"
    TEXT = "#f2f4f8"
    MUTED = "#a8b0bd"
    ACCENT = "#4f8cff"
    BAD = "#ff5c7a"
    BAD_BG = "#3a1822"
    GOOD = "#28c081"
    BORDER = "#2a2f38"

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.title("Settings")
        self.configure(bg=self.BG)
        self.geometry("600x500")

        self.container = tk.Frame(self, bg=self.BG, padx=14, pady=12)
        self.container.pack(fill="both", expand=True)

        self.lists: dict[str, tk.Listbox] = {}

        self._create_section("Target Keywords", "target_keywords")
        self._create_section("Trusted Window Title Keywords", "trusted_window_title_keywords")
        self._create_section("Trusted Process Paths", "trusted_process_paths")

        footer = tk.Frame(self.container, bg=self.BG)
        footer.pack(fill="x", pady=(12, 0))

        save_btn = tk.Button(
            footer, text="Save", command=self.save_and_close,
            bg=self.ACCENT, fg="#ffffff", activebackground="#6fa2ff", activeforeground="#ffffff",
            relief="flat", bd=0, padx=10, pady=5, font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        save_btn.pack(side="right")

    def _create_section(self, label: str, config_key: str) -> None:
        frame = tk.Frame(self.container, bg=self.BG)
        frame.pack(fill="x", pady=(0, 10))

        tk.Label(frame, text=label, bg=self.BG, fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        listbox = tk.Listbox(frame, bg=self.PANEL, fg=self.TEXT, selectbackground=self.ACCENT, relief="flat", bd=0, height=4)
        listbox.pack(fill="x", pady=(4, 4))

        items = getattr(self.config, config_key)
        for item in items:
            listbox.insert("end", item)

        self.lists[config_key] = listbox

        btn_frame = tk.Frame(frame, bg=self.BG)
        btn_frame.pack(fill="x")

        entry = tk.Entry(btn_frame, bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", bd=0)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def add_item() -> None:
            val = entry.get().strip()
            if val:
                listbox.insert("end", val)
                entry.delete(0, "end")

        def remove_item() -> None:
            selection = listbox.curselection()
            if selection:
                listbox.delete(selection[0])

        add_btn = tk.Button(
            btn_frame, text="Add", command=add_item,
            bg=self.PANEL, fg=self.TEXT, activebackground="#242932", activeforeground=self.TEXT,
            relief="flat", bd=0, padx=8, font=("Segoe UI", 9), cursor="hand2"
        )
        add_btn.pack(side="left", padx=(0, 5))

        remove_btn = tk.Button(
            btn_frame, text="Remove Selected", command=remove_item,
            bg=self.PANEL, fg=self.TEXT, activebackground="#242932", activeforeground=self.TEXT,
            relief="flat", bd=0, padx=8, font=("Segoe UI", 9), cursor="hand2"
        )
        remove_btn.pack(side="left")

    def save_and_close(self) -> None:
        for key, listbox in self.lists.items():
            setattr(self.config, key, list(listbox.get(0, "end")))
        self.config.save()
        self.destroy()

class TrayController:
    def __init__(self, app: "AIAgentChatSpellAssistantApp") -> None:
        self.app = app
        self.icon = pystray.Icon(
            "AIChatSpellAssistant",
            self._create_icon_image(),
            APP_TITLE,
            pystray.Menu(
                pystray.MenuItem("Scan AI agent chat", lambda *_: self.app.scan_active_control()),
                pystray.MenuItem("Diagnostics", lambda *_: self.app.show_diagnostics()),
                pystray.MenuItem("Trust current AI agent window", lambda *_: self.app.trust_current_window()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Settings...", lambda *_: self.app.open_settings()),
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
