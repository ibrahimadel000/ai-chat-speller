from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

@dataclass
class TextSnapshot:
    text: str
    source_name: str
    setter: Callable[[str, Misspelling, str], bool] | None
    extraction_method: str
    replace_note: str | None = None

@dataclass
class Misspelling:
    word: str
    start: int
    end: int
    suggestions: list[str]
    context_before: str
    context_after: str
    bounds: tuple[int, int, int, int] | None = None

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
    automation_context: str

@dataclass
class TargetMatch:
    allowed: bool
    reason: str
    info: ActiveWindowInfo
