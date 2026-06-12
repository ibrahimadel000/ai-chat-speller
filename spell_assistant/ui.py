from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Callable, TYPE_CHECKING

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

from spell_assistant.config import APP_TITLE, AppConfig
from spell_assistant.models import Misspelling
from spell_assistant.utils import get_asset_path

if TYPE_CHECKING:
    from spell_assistant.app import AIAgentChatSpellAssistantApp

# Configure CustomTkinter for a modern look
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MainWindow(ctk.CTk):
    BAD = "#ff5c7a"
    ACCENT = "#4f8cff"

    def __init__(self, on_apply: Callable[[str, int], None], on_copy: Callable[[str], None], on_add_word: Callable[[str], None], on_text_changed: Callable[[str], list[Misspelling]]) -> None:
        super().__init__()
        self.on_apply = on_apply
        self.on_copy = on_copy
        self.on_add_word = on_add_word
        self.on_text_changed = on_text_changed
        self.current_misspellings: list[Misspelling] = []
        self.raw_text: str = ""
        self._recheck_after_id: str | None = None
        
        self.title("🪄 AI Spell Assistant")
        
        try:
            self.iconbitmap(get_asset_path("app_icon.ico"))
        except Exception as e:
            logging.warning("Could not set window icon: %s", e)

        self.geometry("600x350")
        self.attributes("-topmost", True)
        
        # We don't want it to close completely if they hit X, just hide it.
        self.protocol("WM_DELETE_WINDOW", self.hide)

        # Main layout container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        # Text Area with built-in scrollbar
        self.text_widget = ctk.CTkTextbox(
            self.container,
            wrap="word",
            font=("Segoe UI", 14)
        )
        self.text_widget.pack(fill="both", expand=True, pady=(0, 16))
        
        # Configure the inner tk.Text tags and bindings
        self.text_widget._textbox.tag_configure("typo", foreground=self.BAD, underline=True)
        self.text_widget._textbox.bind("<Button-3>", self._on_text_click)
        self.text_widget._textbox.bind("<KeyRelease>", self._on_key_release)

        # Footer
        footer = ctk.CTkFrame(self.container, fg_color="transparent")
        footer.pack(fill="x", side="bottom")
        
        hint_label = ctk.CTkLabel(
            footer, 
            text="Right-click underlined words for fixes", 
            text_color="gray60", 
            font=("Segoe UI", 12, "italic")
        )
        hint_label.pack(side="left")

        self.apply_btn = ctk.CTkButton(
            footer, 
            text="Apply & Close", 
            command=self._copy_and_close,
            font=("Segoe UI", 12, "bold"),
            fg_color=self.ACCENT,
            hover_color="#6fa2ff",
            cursor="hand2"
        )
        self.apply_btn.pack(side="right")

        # Context menu for spelling suggestions
        self.menu = tk.Menu(
            self, tearoff=0, bg="#2b2b2b", fg="#f2f4f8", 
            activebackground=self.ACCENT, activeforeground="#ffffff", 
            relief="flat", bd=0, font=("Segoe UI", 10)
        )
        self.bind("<Escape>", lambda e: self.hide())
        
        # Center on screen on first load
        self.eval('tk::PlaceWindow . center')

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
            self.text_widget._textbox.tag_add("typo", start_pos, end_pos)
            self.text_widget._textbox.tag_add(tag_name, start_pos, end_pos)
            
            last_idx = m.end
            
        self.text_widget.insert("end", text[last_idx:])

    def _on_text_click(self, event: tk.Event) -> None:
        try:
            index = self.text_widget._textbox.index(f"@{event.x},{event.y}")
            tags = self.text_widget._textbox.tag_names(index)
        except Exception:
            return
            
        for tag in tags:
            if tag.startswith("typo_"):
                typo_idx = int(tag.split("_")[1])
                misspelling = self.current_misspellings[typo_idx]
                self._show_suggestions(event.x_root, event.y_root, misspelling, typo_idx, tag)
                return

        # Normal text context menu
        self.menu.delete(0, "end")
        self.menu.add_command(label="Copy", command=lambda: self.text_widget._textbox.event_generate("<<Copy>>"))
        self.menu.add_command(label="Paste", command=lambda: self.text_widget._textbox.event_generate("<<Paste>>"))
        self.menu.add_command(label="Select All", command=lambda: self.text_widget._textbox.tag_add("sel", "1.0", "end"))
        self.menu.tk_popup(event.x_root, event.y_root)

    def _show_suggestions(self, x: int, y: int, misspelling: Misspelling, typo_idx: int, tag_name: str) -> None:
        self.menu.delete(0, "end")
        
        if not misspelling.suggestions:
            self.menu.add_command(label="No suggestions", state="disabled")
        else:
            for sugg in misspelling.suggestions:
                def make_cmd(s=sugg, t=typo_idx, tn=tag_name):
                    return lambda: self._apply_suggestion_to_editor(s, t, tn)
                self.menu.add_command(label=sugg, command=make_cmd())
                
        self.menu.add_separator()
        self.menu.add_command(label="Ignore", command=lambda tn=tag_name: self._ignore_typo(tn))
        self.menu.add_command(label="Add to dictionary", command=lambda w=misspelling.word, tn=tag_name: self._add_word(w, tn))
        self.menu.tk_popup(x, y)

    def _add_word(self, word: str, tag_name: str) -> None:
        self.on_add_word(word)
        self._ignore_typo(tag_name)

    def _on_key_release(self, event: tk.Event) -> None:
        if self._recheck_after_id:
            self.after_cancel(self._recheck_after_id)
        current_text = self.text_widget.get("1.0", "end-1c")
        self._recheck_after_id = self.after(300, lambda: self._recheck_text(current_text))

    def _recheck_text(self, text: str) -> None:
        misspellings = self.on_text_changed(text)
        self.current_misspellings = misspellings
        
        for tag in self.text_widget._textbox.tag_names():
            if tag == "typo" or tag.startswith("typo_"):
                self.text_widget._textbox.tag_remove(tag, "1.0", "end")
                
        for i, m in enumerate(misspellings):
            start_idx = self.text_widget._textbox.index(f"1.0 + {m.start} chars")
            end_idx = self.text_widget._textbox.index(f"1.0 + {m.end} chars")
            tag_name = f"typo_{i}"
            self.text_widget._textbox.tag_add("typo", start_idx, end_idx)
            self.text_widget._textbox.tag_add(tag_name, start_idx, end_idx)

    def _apply_suggestion_to_editor(self, suggestion: str, typo_idx: int, tag_name: str) -> None:
        ranges = self.text_widget._textbox.tag_ranges(tag_name)
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
        self._recheck_text(self.text_widget.get("1.0", "end-1c"))
        
    def _ignore_typo(self, tag_name: str) -> None:
        ranges = self.text_widget._textbox.tag_ranges(tag_name)
        if ranges:
            self.text_widget._textbox.tag_remove("typo", ranges[0], ranges[1])
            self.text_widget._textbox.tag_remove(tag_name, ranges[0], ranges[1])

    def _copy_and_close(self) -> None:
        final_text = self.text_widget.get("1.0", "end-1c")
        self.hide()
        self.after(100, lambda: self.on_copy(final_text))

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
        try:
            return Image.open(get_asset_path("app_icon.ico"))
        except Exception as e:
            logging.warning("Could not load tray icon: %s", e)
            image = Image.new("RGBA", (64, 64), (32, 33, 36, 255))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((8, 8, 56, 56), radius=10, fill=(66, 133, 244, 255))
            draw.text((17, 15), "AI", fill=(255, 255, 255, 255))
            draw.line((20, 46, 44, 46), fill=(255, 255, 255, 255), width=4)
            return image
