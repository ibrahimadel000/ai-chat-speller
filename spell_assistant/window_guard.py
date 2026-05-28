from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path

import uiautomation as auto

from spell_assistant.config import AppConfig
from spell_assistant.models import ActiveWindowInfo, TargetMatch
from spell_assistant.utils import _safe_call, PROCESS_QUERY_LIMITED_INFORMATION


class WindowTargetGuard:
    """Allows scans only when the foreground window looks like an AI agent chat target."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def match_active_target(self) -> TargetMatch:
        info = self.active_window_info()
        process_name = info.process_name.lower()
        process_path = info.process_path.lower()
        title = info.title.lower()
        dedicated_processes = {item.lower() for item in self.config.dedicated_ai_process_names}
        if process_name and process_name in dedicated_processes:
            return TargetMatch(True, f"dedicated AI process: {info.process_name}", info)
        trusted_paths = {item.lower() for item in self.config.trusted_process_paths}
        if process_path and process_path in trusted_paths:
            return TargetMatch(True, "trusted AI agent app path", info)
        for keyword in self.config.trusted_window_title_keywords:
            normalized = keyword.strip().lower()
            if normalized and normalized in title:
                return TargetMatch(True, f"trusted AI agent window title: {keyword}", info)

        haystack = "\n".join(
            [
                info.title,
                info.focused_name,
                info.focused_control_type,
                info.focused_class_name,
                info.focused_automation_id,
                info.automation_context,
            ]
        ).lower()
        for keyword in self.config.target_keywords:
            normalized = keyword.strip().lower()
            if normalized and normalized in haystack:
                return TargetMatch(True, f"AI agent chat keyword: {keyword}", info)

        return TargetMatch(False, "active window/control did not match AI agent chat targets", info)

    def describe_active_target(self) -> str:
        match = self.match_active_target()
        info = match.info
        return "\n".join(
            [
                f"AI agent chat target: {'yes' if match.allowed else 'no'}",
                f"Reason: {match.reason}",
                f"Window title: {info.title or '(empty)'}",
                f"Process: {info.process_name or '(unknown)'}",
                f"Process path: {info.process_path or '(unknown)'}",
                f"Focused name: {info.focused_name or '(empty)'}",
                f"Focused type: {info.focused_control_type or '(unknown)'}",
                f"Focused class: {info.focused_class_name or '(unknown)'}",
                f"Focused AutomationId: {info.focused_automation_id or '(empty)'}",
                f"Automation context: {info.automation_context or '(empty)'}",
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
            automation_context=self._automation_context(control),
        )

    @staticmethod
    def _automation_context(control) -> str:
        parts = []
        current = control
        for _ in range(8):
            if current is None:
                break
            name = _safe_call("", lambda: current.Name) or ""
            control_type = _safe_call("", lambda: current.ControlTypeName) or ""
            class_name = _safe_call("", lambda: current.ClassName) or ""
            automation_id = _safe_call("", lambda: current.AutomationId) or ""
            parts.append(" ".join(item for item in [name, control_type, class_name, automation_id] if item))
            current = _safe_call(None, current.GetParentControl)
        return " | ".join(part for part in parts if part)

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
    """Reports focused-control metadata only; it does not scan arbitrary fields."""

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
            f"ValuePattern: {'yes' if _safe_call(None, getattr, control, 'GetValuePattern', None) else 'no'}",
            f"TextPattern: {'yes' if _safe_call(None, getattr, control, 'GetTextPattern', None) else 'no'}",
        ]
        return "\n".join(lines)
