# AI Agent Chat Spell Assistant 🪄

**The missing spell-checker for AI coding assistants and CLI tools.**

Have you ever noticed that powerful AI coding agents (like Antigravity, Codex, Cursor, and various AI CLI tools) often lack native spell-checking in their chat input boxes? You end up sending prompts with typos, which can confuse the AI or just feel frustrating to read.

This lightweight Windows utility solves exactly that. It provides a targeted, smart spell-checker that **only activates inside your configured AI agent chats and CLI tools**, completely ignoring your regular browsers, IDEs, and system menus so it never gets in your way.

## ✨ Features

- **Hyper-Targeted:** Refuses to scan ordinary apps. It only activates when your focused window or control matches your AI chat keywords (e.g., `codex`, `antigravity`, `ai agent`).
- **Smart Code Filtering:** Built for developers. Automatically ignores URLs, email addresses, file paths, `camelCaseVariables`, inline code, fenced code blocks, and ALL_CAPS constants.
- **Real-Time Corrections:** Provides a sleek popup editor with real-time red underlines for typos.
- **Right-Click Dictionary:** Right-click any typo to see suggestions, ignore it, or add it to your personal offline dictionary.
- **Lightning Fast & Private:** Uses the blazing-fast `symspellpy` dictionary locally. Your prompts are never sent to the cloud.
- **System Tray Integration:** Runs quietly in the background without cluttering your taskbar.

---

## 🚀 Installation & Usage

Because AI tools are often custom Electron apps or terminal interfaces without native spell-check APIs, this assistant uses a smart UI Automation and clipboard approach to seamlessly read and replace your text.

### Quick Start

If you just want to run the pre-configured environment, use the included VBS scripts in the **`launchers`** folder:
- **`Start AI Agent Chat Spell Assistant.vbs`** - Starts the utility silently in the background.
- **`Create Desktop Shortcut.vbs`** - Creates a handy shortcut on your desktop.

### Building from Source

To build the standalone `.exe` yourself:
1. Ensure you have Python installed (Windows only).
2. Run the build script:
   ```powershell
   .\build.ps1
   ```
3. The executable will be generated at `dist\AIAgentChatSpellAssistant.exe`.

---

## ⌨️ How to Use It

1. Start the app (it will appear in your system tray).
2. Click inside your favorite AI agent chat input or AI CLI tool.
3. Press **`Alt + Q`** (Default scan hotkey).
4. The overlay instantly appears, highlighting any misspelled words.
5. **Right-click** a red-underlined word to pick a correction, or select **Add to dictionary** to remember it forever.
6. Click **Copy Text** (or press Enter) to instantly paste the corrected text back into your chat.

### Hotkeys

- **`Alt + Q`**: Scan the current input field for typos.
- **`Alt + W`**: Quick Fix (automatically apply the best suggestion for the first typo).
- **`Esc`**: Hide the overlay without making any changes.

*(Hotkeys can be easily customized in `settings.json`)*

---

## ⚙️ Adding New AI Tools

By default, the assistant looks for keywords like `antigravity`, `codex`, and `agent chat`. 

**What if your AI CLI or Chat isn't recognized?**
1. Open `settings.json`.
2. Add a unique keyword representing your AI tool's window title to the `"target_keywords"` list, or add its executable name to `"dedicated_ai_process_names"`.
3. Restart the app.

---

## 📝 Notes & Limitations

- **Windows Only:** Relies heavily on native Windows UI Automation and `ctypes` hotkeys.
- **Clipboard Mechanism:** The app scans by doing a rapid select-all, copy, and restore sequence. Because of this, rich text formatting in the input box might be converted to plain text during correction.
- **Dictionary Storage:** Custom words added via the right-click menu are saved locally in `user_words.txt`.
