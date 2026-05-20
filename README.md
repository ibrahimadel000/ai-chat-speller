# Windows Spell Overlay MVP

A small Python prototype for checking text in the currently focused Windows input control. It uses Windows UI Automation for text extraction, `pyspellchecker` for offline spelling suggestions, and a tiny Tkinter overlay for corrections.

This is now aimed at Electron chat/editor workflows first: UI Automation is still available, but the clipboard fallback is the important path for VS Code, Codex-style chats, and Antigravity-style custom editors.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python spell_overlay.py
```

## Build an EXE

```powershell
.\build.ps1
```

The executable is written to `dist\SpellOverlay.exe`. The build uses PyInstaller and collects `pyspellchecker` dictionary data.

## Usage

1. Start the app.
2. Click into a text box in another app, such as VS Code, an Electron chat view, or a browser text area.
3. Press `Ctrl+Alt+S` for the normal Windows UI Automation scan.
4. Press `Ctrl+Alt+Shift+S` if the normal scan cannot see text in an Electron or Monaco editor.
5. Press `Ctrl+Alt+D` to show focused-control diagnostics.
6. Press `Ctrl+Alt+P` to pause/resume scans while keeping the utility open.
7. Click a suggested correction in the overlay, or use `Ignore` / `Add word` for false positives.

The app also adds a system tray icon with scan, diagnostics, pause/resume, hide, and exit actions.

If the focused control exposes a writable UI Automation value pattern, the MVP replaces the misspelled word in the whole field. If the target app does not allow writing through accessibility, the selected suggestion is copied to the clipboard instead.

The clipboard fallback deliberately sends `Ctrl+A`, `Ctrl+C`, and later `Ctrl+A`, `Ctrl+V` when applying a correction. This makes it useful for Electron editors that hide text from UI Automation, but it also means it rewrites the active field with the corrected full text. Use it only after clicking inside the input you want to check.

Press `Esc` to hide the overlay.

## Settings and Logs

On first run, the app creates:

- `settings.json` for hotkeys, startup message, clipboard timing, and extra known words.
- `spell_overlay.log` for scan results and focused-control diagnostics.
- `user_words.txt` after the first `Add word` action.

If the clipboard fallback does not work smoothly in a specific app, open `settings.json` and slightly increase the clipboard timing values.

## Notes and Limits

- This is intentionally local and offline after dependencies are installed.
- Electron apps vary in what they expose through Windows accessibility APIs. Some chat editors expose text cleanly; some custom editors expose only partial text or no writable pattern.
- VS Code's Monaco editor often does not behave like a normal Windows text box. Use `Ctrl+Alt+Shift+S` for the clipboard fallback.
- The clipboard fallback restores text clipboard content, but Windows clipboard formats such as images or rich text may be replaced by plain text during the scan.
- `Add word` stores lowercase entries in `user_words.txt` next to the script and loads them on startup.
- `pynput` global hotkeys may need the script to run in the same privilege level as the target application. If the target app is elevated, run this utility elevated too.
- The default dictionary is English. `pyspellchecker` supports other language dictionaries, but they must be configured explicitly.
