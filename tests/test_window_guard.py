import pytest
from spell_assistant.window_guard import WindowTargetGuard, ActiveWindowInfo, TargetMatch
from spell_assistant.config import AppConfig

@pytest.fixture
def guard():
    config = AppConfig(
        target_keywords=["ai chat", "antigravity", "codex"],
        dedicated_ai_process_names=["aichat.exe"],
        trusted_window_title_keywords=[],
        trusted_process_paths=[]
    )
    return WindowTargetGuard(config)

def test_target_guard_dedicated_process(guard: WindowTargetGuard):
    info = ActiveWindowInfo(
        hwnd=123,
        title="Some Random Title",
        process_id=456,
        process_name="aichat.exe",
        process_path="C:\\Program Files\\AIChat\\aichat.exe",
        focused_name="",
        focused_control_type="",
        focused_class_name="",
        focused_automation_id="",
        automation_context=""
    )
    guard.active_window_info = lambda: info
    match = guard.match_active_target()
    assert match.allowed is True
    assert "dedicated AI process" in match.reason

def test_target_guard_keywords_in_title(guard: WindowTargetGuard):
    info = ActiveWindowInfo(
        hwnd=123,
        title="Antigravity Workspace",
        process_id=456,
        process_name="chrome.exe",
        process_path="C:\\Chrome\\chrome.exe",
        focused_name="",
        focused_control_type="",
        focused_class_name="",
        focused_automation_id="",
        automation_context=""
    )
    guard.active_window_info = lambda: info
    match = guard.match_active_target()
    assert match.allowed is True
    assert "keyword" in match.reason

def test_target_guard_disallowed(guard: WindowTargetGuard):
    info = ActiveWindowInfo(
        hwnd=123,
        title="Google Search - Google Chrome",
        process_id=456,
        process_name="chrome.exe",
        process_path="C:\\Chrome\\chrome.exe",
        focused_name="Search box",
        focused_control_type="Edit",
        focused_class_name="Chrome_RenderWidgetHostHWND",
        focused_automation_id="search",
        automation_context=""
    )
    guard.active_window_info = lambda: info
    match = guard.match_active_target()
    assert match.allowed is False
