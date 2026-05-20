from __future__ import annotations

from spell_assistant.utils import configure_logging, ensure_single_instance
from spell_assistant.app import AIAgentChatSpellAssistantApp

if __name__ == "__main__":
    configure_logging()
    if ensure_single_instance():
        AIAgentChatSpellAssistantApp().run()
