# AI Chat Spell Assistant

A lightweight Windows utility for checking spelling only inside AI agent chat inputs, such as Codex, Antigravity, ChatGPT, and similar assistant chat boxes.

The app is intentionally not a general OS spell checker. Before scanning, it checks whether the active window or focused control looks like a configured AI chat target. If not, it refuses to scan and does not touch the clipboard.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python spell_overlay.py
```

## Double-Click Launch

Use these files from File Explorer:

- `Start AI Chat Spell Assistant.vbs` starts the utility silently with no command window.
- `Open Project Folder.vbs` opens this folder.
- `Open Project in VS Code.vbs` opens the folder in VS Code if the `code` command is installed.
- `Create Desktop Shortcut.vbs` creates an `AI Chat Spell Assistant` shortcut on your desktop.

## Build an EXE

```powershell
.\build.ps1
```

The executable is written to `dist\AIChatSpellAssistant.exe`. The build uses PyInstaller and collects `pyspellchecker` dictionary data.

## Usage

1. Start the app.
2. Click inside the AI agent chat input you want to check.
3. Press `Ctrl+Alt+S` to scan the focused AI chat input. This is clipboard-first because AI chat apps are usually Electron/custom editors.
4. Press `Ctrl+Alt+Shift+S` to force the AI chat clipboard scan.
5. Press `Ctrl+Alt+D` to show focused-control diagnostics.
6. Press `Ctrl+Alt+P` to pause/resume scans while keeping the utility open.
7. Click a suggested correction in the overlay, or use `Ignore` / `Add word` for false positives.

The app also adds a system tray icon with AI chat scan, diagnostics, pause/resume, hide, and exit actions.

If the focused AI chat input supports direct accessibility replacement, the app can use that. For Electron chat inputs, it normally uses `Ctrl+A`, `Ctrl+C`, and later `Ctrl+A`, `Ctrl+V` inside the focused AI chat input.

If the active app does not match an AI chat target, the app shows `AI chat target not detected` and does nothing.

Press `Esc` to hide the overlay.

## Settings and Logs

On first run, the app creates:

- `settings.json` for hotkeys, startup message, clipboard timing, and extra known words.
- `spell_overlay.log` for scan results and focused-control diagnostics.
- `user_words.txt` after the first `Add word` action.

Use `target_keywords` and `dedicated_ai_process_names` in `settings.json` to control which AI chat surfaces are allowed. If a new chat app is blocked, press `Ctrl+Alt+D`, look at the window title/process/focused name, then add a narrow keyword such as `codex`, `antigravity`, or the exact app name.

If the clipboard fallback does not work smoothly in a specific AI chat app, slightly increase the clipboard timing values.

## Notes and Limits

- This is intentionally local and offline after dependencies are installed.
- The app only scans configured AI chat targets.
- Electron apps vary in what they expose through Windows accessibility APIs. AI chat editors often need the clipboard path.
- The clipboard fallback restores text clipboard content, but Windows clipboard formats such as images or rich text may be replaced by plain text during the scan.
- `Add word` stores lowercase entries in `user_words.txt` next to the script and loads them on startup.
- `pynput` global hotkeys may need the script to run in the same privilege level as the target application. If the target app is elevated, run this utility elevated too.
- The default dictionary is English. `pyspellchecker` supports other language dictionaries, but they must be configured explicitly.
