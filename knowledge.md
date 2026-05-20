# AI Agent Chat Spell Assistant

## What it is
A lightweight Windows-only utility that checks spelling **only inside AI agent chat inputs** (Codex, Antigravity, etc.). It refuses to scan ordinary apps/browsers/editors unless the focused control matches configured AI agent chat target rules.

## Key files
- `spell_overlay.py` — single-file application logic (main entry point)
- `settings.json` — all configuration (hotkeys, target keywords, delays, trusted windows)
- `user_words.txt` — user-added dictionary words (auto-created)
- `build.ps1` — PyInstaller build script
- `requirements.txt` — runtime dependencies
- `requirements-build.txt` — PyInstaller dependency

## Commands
- **Run:** `python spell_overlay.py`
- **Install deps:** `pip install -r requirements.txt`
- **Build exe:** `.\build.ps1` (generates `dist\AIAgentChatSpellAssistant.exe`)

## Architecture
Single-file app using Python stdlib + these libraries:
- **tkinter** — overlay UI window
- **pynput** — keyboard simulation (Copy/Paste)
- **pyperclip** — clipboard read/write
- **pystray + Pillow** — system tray icon
- **uiautomation** — Windows UI Automation (focused control detection)
- **pyspellchecker** — offline spell checker
- **ctypes** — native Windows hotkey API (alternative to pynput hooks)

## Key behaviors
- Before scanning, the `WindowTargetGuard` checks the foreground window against `target_keywords`, `dedicated_ai_process_names`, `trusted_window_title_keywords`, and `trusted_process_paths`.
- Scans by: selecting all (Ctrl+A), copying (Ctrl+C), reading clipboard, then restoring original clipboard content.
- Applies corrections by: copying new text to clipboard, selecting all (Ctrl+A), pasting (Ctrl+V).
- Detector intelligently skips URLs, email addresses, code blocks, file paths, camelCase identifiers, short/all-caps words, words with digits, and possessive forms.
- `Ctrl+Alt+S` triggers scan, `Ctrl+Alt+D` shows diagnostics, `Ctrl+Alt+P` pauses/resumes.

## Notable constraints
- **Windows-only** — uses Windows-specific APIs (ctypes, uiautomation, win32 hotkeys)
- **Single instance** — uses a mutex (`CreateMutexW`) to prevent multiple instances
- **Settings auto-save** — modifications via "Trust" feature persist to `settings.json`
- **Rolling log file** — `spell_overlay.log` with 3 backups of 500KB each
- Clipboard rich format may be lost (plain text only restoration)
- Hotkey conflicts with other apps are reported at startup

## Gotchas
- `settings.json` is read on startup only; changes require a restart
- The `WindowTargetGuard.describe_active_target()` and `AccessibilityReader.describe_focused_control()` are the key debugging tools (hotkey: Ctrl+Alt+D)
- If `Ctrl+Alt+S` does nothing, check for hotkey conflicts with other apps or change the hotkey in settings.json
- The app runs in the system tray, not as a visible window
