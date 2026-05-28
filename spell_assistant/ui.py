from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Callable, TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from spell_assistant.config import APP_TITLE, AppConfig
from spell_assistant.models import Misspelling

if TYPE_CHECKING:
    from spell_assistant.app import AIAgentChatSpellAssistantApp

class MainWindow(tk.Tk):
    BG = "#1e1e1e"
    TEXT = "#f2f4f8"
    ACCENT = "#4f8cff"
    BAD = "#ff5c7a"
    BORDER = "#2c2c2c"

    def __init__(self, on_apply: Callable[[str, int], None], on_copy: Callable[[str], None]) -> None:
        super().__init__()
        self.on_apply = on_apply
        self.on_copy = on_copy
        self.current_misspellings: list[Misspelling] = []
        self.raw_text: str = ""
        
        self.title("Spell Checker")
        self.geometry("450x150")
        self.attributes("-topmost", True)
        self.configure(bg=self.BORDER)
        
        # We don't want it to close completely if they hit X, just maybe hide? Or they can close it and Alt+Q brings it back.
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.container = tk.Frame(self, bg=self.BG, padx=4, pady=4)
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        # A little header
        header = tk.Frame(self.container, bg=self.BG)
        header.pack(fill="x", pady=(0, 4))
        tk.Label(header, text="Copied Text (Fix typos and copy)", bg=self.BG, fg="#a8b0bd", font=("Segoe UI", 9)).pack(side="left")

        self.text_widget = tk.Text(
            self.container,
            wrap="word",
            bg=self.BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground=self.ACCENT,
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=("Segoe UI", 11),
            height=4
        )
        self.text_widget.pack(fill="both", expand=True)
        self.text_widget.tag_configure("typo", foreground=self.BAD, underline=True)
        self.text_widget.bind("<Button-1>", self._on_text_click)

        footer = tk.Frame(self.container, bg=self.BG)
        footer.pack(fill="x", pady=(4, 0))

        tk.Button(
            footer, text="Copy Text", command=self._copy_and_close,
            bg=self.ACCENT, fg="#ffffff", activebackground="#6fa2ff", activeforeground="#ffffff",
            relief="flat", bd=0, padx=12, pady=4, font=("Segoe UI", 9, "bold"), cursor="hand2"
        ).pack(side="right")

        self.menu = tk.Menu(self, tearoff=0, bg="#2d2d2d", fg=self.TEXT, activebackground=self.ACCENT, activeforeground="#ffffff", relief="flat", bd=0)
        self.bind("<Escape>", lambda e: self.hide())

    def show_text(self, text: str, misspellings: list[Misspelling]) -> None:
        self.raw_text = text
        self.current_misspellings = misspellings
        self._render_text()
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self) -> None:
        self.withdraw()

    def _render_text(self) -> None:
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")

        text = self.raw_text
        last_idx = 0
        
        for i, m in enumerate(self.current_misspellings):
            self.text_widget.insert("end", text[last_idx:m.start])
            
            start_pos = self.text_widget.index("end-1c")
            self.text_widget.insert("end", m.word)
            end_pos = self.text_widget.index("end-1c")
            
            tag_name = f"typo_{i}"
            self.text_widget.tag_add("typo", start_pos, end_pos)
            self.text_widget.tag_add(tag_name, start_pos, end_pos)
            
            last_idx = m.end
            
        self.text_widget.insert("end", text[last_idx:])

    def _on_text_click(self, event: tk.Event) -> None:
        index = self.text_widget.index(f"@{event.x},{event.y}")
        tags = self.text_widget.tag_names(index)
        
        for tag in tags:
            if tag.startswith("typo_"):
                typo_idx = int(tag.split("_")[1])
                misspelling = self.current_misspellings[typo_idx]
                self._show_suggestions(event.x_root, event.y_root, misspelling, typo_idx, tag)
                return

    def _show_suggestions(self, x: int, y: int, misspelling: Misspelling, typo_idx: int, tag_name: str) -> None:
        self.menu.delete(0, "end")
        
        if not misspelling.suggestions:
            self.menu.add_command(label="No suggestions", state="disabled")
        else:
            for sugg in misspelling.suggestions:
                def make_cmd(s=sugg, t=typo_idx, tn=tag_name):
                    return lambda: self._apply_suggestion_to_editor(s, t, tn)
                self.menu.add_command(label=s, command=make_cmd())
                
        self.menu.add_separator()
        self.menu.add_command(label="Ignore", command=lambda tn=tag_name: self._ignore_typo(tn))
        self.menu.tk_popup(x, y)

    def _apply_suggestion_to_editor(self, suggestion: str, typo_idx: int, tag_name: str) -> None:
        ranges = self.text_widget.tag_ranges(tag_name)
        if not ranges:
            return
        
        start, end = ranges[0], ranges[1]
        
        original = self.text_widget.get(start, end)
        if original.isupper():
            suggestion = suggestion.upper()
        elif original[:1].isupper():
            suggestion = suggestion.capitalize()
            
        self.text_widget.configure(state="normal")
        self.text_widget.delete(start, end)
        self.text_widget.insert(start, suggestion)
        
        self.on_apply(suggestion, typo_idx)
        
    def _ignore_typo(self, tag_name: str) -> None:
        ranges = self.text_widget.tag_ranges(tag_name)
        if ranges:
            self.text_widget.tag_remove("typo", ranges[0], ranges[1])
            self.text_widget.tag_remove(tag_name, ranges[0], ranges[1])

    def _copy_and_close(self) -> None:
        final_text = self.text_widget.get("1.0", "end-1c")
        self.on_copy(final_text)
        # Keep window open or hide it? User said "small text box, which i see it in the background".
        # So maybe don't even close it. Just give visual feedback.
        self.title("Copied!")
        self.after(1000, lambda: self.title("Spell Checker"))

class TrayController:
    def __init__(self, app: "AIAgentChatSpellAssistantApp") -> None:
        self.app = app
        self.icon = pystray.Icon(
            "AIChatSpellAssistant",
            self._create_icon_image(),
            APP_TITLE,
            pystray.Menu(
                pystray.MenuItem("Show Editor", lambda *_: self.app.show_editor()),
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
