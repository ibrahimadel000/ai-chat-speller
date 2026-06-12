from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

APP_TITLE = "AI Agent Chat Spell Assistant"
APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "spell_overlay.log"
USER_WORDS_FILE = APP_DIR / "user_words.txt"
USER_BIGRAMS_FILE = APP_DIR / "user_bigrams.txt"

HOTKEY_SCAN = "<alt>+q"
HOTKEY_QUICK_FIX = "<alt>+w"
HOTKEY_DIAGNOSTICS = "<ctrl>+<alt>+d"
HOTKEY_PAUSE = "<ctrl>+<alt>+p"
HOTKEY_HIDE = "<esc>"
CLIPBOARD_COPY_DELAY_SECONDS = 0.12
CLIPBOARD_FOCUS_DELAY_SECONDS = 0.15
CLIPBOARD_PASTE_DELAY_SECONDS = 0.08
CLIPBOARD_WAIT_TIMEOUT_SECONDS = 1.2

DEFAULT_KNOWN_WORDS = {
    "api", "chatgpt", "codex", "electron", "github",
    "javascript", "json", "monaco", "npm", "openai",
    "powershell", "python", "typescript", "uiautomation", "vscode",
    "args", "kwargs", "config", "utils", "repo", "init", "dev", "devops",
    "linux", "localhost", "url", "html", "css", "auth", "sudo", "gui",
    "tcp", "udp", "dns", "sql", "backend", "frontend", "ui", "db",
    "yaml", "toml", "dll", "exe", "venv", "src", "lib", "pwd", "cwd",
    "cmd", "os", "env", "dotenv", "docker", "kubernetes", "nginx",
    "apache", "ssl", "tls", "ssh", "rsa", "aes", "md5", "sha", "utf",
    "ascii", "regex", "sdk", "cli", "uuid", "guid", "bool", "int", "str",
    "dict", "dicts", "tuples", "tuple", "func", "req", "params", "res",
    "postgres", "sqlite", "mysql", "mongo", "redis", "aws", "gcp", "azure",
    "ip", "http", "https", "wss", "ws", "graphql", "grpc", "rest", "restful",
    "apis", "rpc", "ux", "oauth", "jwt", "cors", "xss", "csrf", "nosql",
    "xml", "csv", "md", "svg", "png", "jpg", "jpeg", "gif", "mp3", "mp4",
    "wav", "flac", "avi", "mkv", "webm", "rar", "zip", "tar", "gz", "bz",
    "xz", "7z", "pkg", "deb", "rpm", "apk", "msi", "dmg", "iso", "img",
    "bin", "cue", "raw", "vmdk", "vdi", "vhd", "qcow", "ova", "ovf",
    "boolean", "integer", "string", "character", "char", "float", "double",
}

DEFAULT_TARGET_KEYWORDS = [
    "antigravity", "codex", "ai agent", "agent mode",
    "ask ai", "ask codex", "codex chat", "antigravity chat", "agent chat",
]

DEFAULT_DEDICATED_AI_PROCESSES = [
    "antigravity.exe", "codex.exe",
]

@dataclass
class AppConfig:
    hotkey_scan: str = HOTKEY_SCAN
    hotkey_quick_fix: str = HOTKEY_QUICK_FIX
    hotkey_diagnostics: str = HOTKEY_DIAGNOSTICS
    hotkey_pause: str = HOTKEY_PAUSE
    hotkey_hide: str = HOTKEY_HIDE
    clipboard_copy_delay_seconds: float = CLIPBOARD_COPY_DELAY_SECONDS
    clipboard_focus_delay_seconds: float = CLIPBOARD_FOCUS_DELAY_SECONDS
    clipboard_paste_delay_seconds: float = CLIPBOARD_PASTE_DELAY_SECONDS
    clipboard_wait_timeout_seconds: float = CLIPBOARD_WAIT_TIMEOUT_SECONDS
    startup_message: bool = True
    extra_known_words: list[str] = field(default_factory=list)
    target_keywords: list[str] = field(default_factory=lambda: DEFAULT_TARGET_KEYWORDS.copy())
    dedicated_ai_process_names: list[str] = field(default_factory=lambda: DEFAULT_DEDICATED_AI_PROCESSES.copy())
    trusted_window_title_keywords: list[str] = field(default_factory=list)
    trusted_process_paths: list[str] = field(default_factory=list)
    max_chat_input_chars: int = 12000

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "AppConfig":
        defaults = cls()
        if not path.exists():
            path.write_text(json.dumps(defaults.to_json(), indent=2) + "\n", encoding="utf-8")
            return defaults

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Failed to read settings.json; using defaults")
            return defaults
        if not isinstance(raw, dict):
            logging.warning("settings.json did not contain an object; using defaults")
            return defaults

        values = defaults.to_json()
        values.update({key: value for key, value in raw.items() if key in values})
        config = cls(**values)
        if raw != config.to_json():
            path.write_text(json.dumps(config.to_json(), indent=2) + "\n", encoding="utf-8")
        return config

    def to_json(self) -> dict[str, object]:
        return {
            "hotkey_scan": self.hotkey_scan,
            "hotkey_quick_fix": self.hotkey_quick_fix,
            "hotkey_diagnostics": self.hotkey_diagnostics,
            "hotkey_pause": self.hotkey_pause,
            "hotkey_hide": self.hotkey_hide,
            "clipboard_copy_delay_seconds": self.clipboard_copy_delay_seconds,
            "clipboard_focus_delay_seconds": self.clipboard_focus_delay_seconds,
            "clipboard_paste_delay_seconds": self.clipboard_paste_delay_seconds,
            "clipboard_wait_timeout_seconds": self.clipboard_wait_timeout_seconds,
            "startup_message": self.startup_message,
            "extra_known_words": self.extra_known_words,
            "target_keywords": self.target_keywords,
            "dedicated_ai_process_names": self.dedicated_ai_process_names,
            "trusted_window_title_keywords": self.trusted_window_title_keywords,
            "trusted_process_paths": self.trusted_process_paths,
            "max_chat_input_chars": self.max_chat_input_chars,
        }

    def save(self, path: Path = SETTINGS_FILE) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")
