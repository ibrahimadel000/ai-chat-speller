import pytest
from pathlib import Path
from spell_assistant.engine import SpellEngine
from spell_assistant.models import Misspelling

@pytest.fixture
def engine(tmp_path: Path):
    user_words_file = tmp_path / "user_words.txt"
    # Create engine with a temporary user words file and a few known words
    return SpellEngine(user_words_path=user_words_file, extra_known_words=["pytest", "antigravity"])

def test_find_misspellings_basic(engine: SpellEngine):
    text = "this is a tst message"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 1
    assert misspellings[0].word == "tst"
    assert misspellings[0].start == 10
    assert misspellings[0].end == 13

def test_skips_urls(engine: SpellEngine):
    text = "Visit https://google.com for more info"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 0

def test_skips_camel_case(engine: SpellEngine):
    text = "this is a camelCaseVariable and AnotherOne"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 0

def test_skips_code_blocks(engine: SpellEngine):
    text = "here is some code: `import asdfghjkl` and it should be ignored"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 0
    
    text_fenced = "code block: ```\nvar foo = barx;\n```"
    misspellings = engine.find_misspellings(text_fenced)
    assert len(misspellings) == 0

def test_skips_words_with_numbers(engine: SpellEngine):
    text = "my variable is var123xy and it works"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 0

def test_skips_emails_and_paths(engine: SpellEngine):
    text = "email me at user@example.com or see C:\\path\\to\\file.txt"
    misspellings = engine.find_misspellings(text)
    assert len(misspellings) == 0

def test_add_word(engine: SpellEngine):
    text = "this is a zxcvbnm word"
    assert len(engine.find_misspellings(text)) == 1
    
    # Add word
    engine.add_word("zxcvbnm")
    
    # Re-evaluate
    assert len(engine.find_misspellings(text)) == 0

    # Ensure it was saved to the temp path
    assert "zxcvbnm" in engine.user_words_path.read_text()
