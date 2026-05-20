# AI Agent Chat Spell Assistant

A lightweight Windows utility that checks spelling only inside AI agent chat inputs, such as Codex chat and Antigravity agent chat.

This is not a general spell checker. It refuses to scan ordinary apps, browsers, editors, and random text boxes unless the active focused area matches the configured AI agent chat target rules.

## Double-Click Launch

Use these files from File Explorer:

- `Start AI Agent Chat Spell Assistant.vbs` starts the utility silently with no command window.
- `Create Desktop Shortcut.vbs` creates an `AI Agent Chat Spell Assistant` shortcut on your desktop.
- `Open Project Folder.vbs` opens this folder.
- `Open Project in VS Code.vbs` opens the project folder in VS Code if the `code` command is installed.

## Usage

1. Start the app.
2. Click inside the Codex or Antigravity agent chat input.
3. Press `Ctrl+Alt+S`.
4. The overlay highlights the wrong word in context.
5. Pick a correction, or use `Ignore` / `Add word`.

Other hotkeys:

- `Ctrl+Alt+D` shows AI agent chat target diagnostics.
- `Ctrl+Alt+P` pauses/resumes the assistant.
- `Esc` hides the overlay.
- `Enter` applies the first suggestion while the overlay is focused.
- `1` through `5` apply a numbered suggestion.

If `Ctrl+Alt+S` does not fire, the startup overlay will report a hotkey registration problem. That usually means another app already owns the shortcut. Change `hotkey_scan` in `settings.json`, or use the tray menu action `Scan AI agent chat`.

If you double-click the launcher and nothing seems to happen, check the tray. The assistant runs as one background instance; double-clicking again will show a message instead of starting a second copy.

## How It Stays AI-Agent-Only

Before it scans, the app checks the foreground window and focused accessibility context for configured AI-agent-chat keywords such as `codex`, `antigravity`, `ai agent`, `ask codex`, and `agent chat`.

If the focused area does not match, it shows `AI agent chat target not detected` and does not copy, scan, or replace anything.

If the blocked window is actually Codex or Antigravity agent chat, click `Trust this AI agent window` in the overlay. The app stores that exact window/process in `settings.json`.

## Settings

`settings.json` controls the allowed AI agent chat targets:

- `target_keywords` controls accepted window/control/context words.
- `dedicated_ai_process_names` controls accepted dedicated app process names.
- `trusted_window_title_keywords` and `trusted_process_paths` are filled when you trust a blocked AI-agent window.
- `max_chat_input_chars` prevents accidentally scanning a large editor/document.

For a new AI agent chat app, press `Ctrl+Alt+D` while focused in the chat input and add a narrow keyword from the diagnostics to `target_keywords`.

## Notes

- The assistant uses clipboard shortcuts because AI agent chats are usually Electron/custom editors.
- The detector skips code-ish text such as URLs, inline code, file paths, acronyms, camelCase identifiers, and words with numbers.
- The clipboard text content is restored after scanning, but rich clipboard formats may become plain text.
- The dictionary is offline via `pyspellchecker`.
- `Add word` stores lowercase entries in `user_words.txt`.
