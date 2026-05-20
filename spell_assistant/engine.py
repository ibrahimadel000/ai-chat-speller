from __future__ import annotations

import re
from pathlib import Path
import os
import symspellpy

from symspellpy import SymSpell, Verbosity

from spell_assistant.config import DEFAULT_KNOWN_WORDS, USER_WORDS_FILE
from spell_assistant.models import Misspelling

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']{1,}")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
FILE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|\.{0,2}/|\.{0,2}\\)[^\s]+")
MARKDOWN_HEADER_RE = re.compile(r"^#+ .*", re.MULTILINE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
ALL_CAPS_CONSTANT_RE = re.compile(r"\b[A-Z_]+\b")


class SpellEngine:
    def __init__(self, user_words_path: Path = USER_WORDS_FILE, extra_known_words: list[str] | None = None) -> None:
        self.sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        self.user_words_path = user_words_path
        
        dictionary_path = os.path.join(os.path.dirname(symspellpy.__file__), "frequency_dictionary_en_82_765.txt")
        self.sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
        
        self._load_words(DEFAULT_KNOWN_WORDS)
        if extra_known_words:
            self._load_words(extra_known_words)
        self._load_user_words()

    def _load_words(self, words: list[str]) -> None:
        for word in words:
            normalized = self._normalize_word(word)
            if normalized:
                self.sym_spell.create_dictionary_entry(normalized, 100)

    def find_misspellings(self, text: str) -> list[Misspelling]:
        skip_spans = self._skip_spans(text)
        matches = list(WORD_RE.finditer(text))
        
        misspellings: list[Misspelling] = []
        for match in matches:
            word = match.group(0)
            normalized = self._normalize_word(word)
            
            if self._should_skip_match(text, match, skip_spans):
                continue
                
            exact_matches = self.sym_spell.lookup(normalized, Verbosity.TOP, max_edit_distance=0)
            is_known = len(exact_matches) > 0

            if not is_known:
                context_before, context_after = self._context(text, match.start(), match.end())
                suggestions = self._suggestions(word)
                misspellings.append(
                    Misspelling(
                        word=word,
                        start=match.start(),
                        end=match.end(),
                        suggestions=suggestions,
                        context_before=context_before,
                        context_after=context_after,
                    )
                )
        return misspellings

    def _suggestions(self, word: str) -> list[str]:
        normalized = self._normalize_word(word)
        suggestions = self.sym_spell.lookup(normalized, Verbosity.CLOSEST, max_edit_distance=2)
        return [s.term for s in suggestions][:5]

    def _skip_spans(self, text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        for pattern in [FENCED_CODE_RE, INLINE_CODE_RE, URL_RE, EMAIL_RE, FILE_PATH_RE, MARKDOWN_HEADER_RE, HTML_TAG_RE, ALL_CAPS_CONSTANT_RE]:
            spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
        return spans

    def _should_skip_match(self, text: str, match: re.Match[str], skip_spans: list[tuple[int, int]]) -> bool:
        start, end = match.start(), match.end()
        word = match.group(0)
        normalized = self._normalize_word(word)
        if not normalized or len(normalized) <= 2:
            return True
        if any(start < span_end and end > span_start for span_start, span_end in skip_spans):
            return True
        if "'" in word:
            return True
        if any(char.isdigit() for char in word):
            return True
        if word.isupper() and len(word) <= 6:
            return True
        if self._looks_like_camel_or_identifier(word):
            return True
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if (before and before in "._/\\-#") or (after and after in "._/\\-"):
            return True
        return False

    @staticmethod
    def _looks_like_camel_or_identifier(word: str) -> bool:
        if "_" in word:
            return True
        if not any(char.isupper() for char in word[1:]):
            return False
        return not word.istitle()

    @staticmethod
    def _context(text: str, start: int, end: int, radius: int = 70) -> tuple[str, str]:
        before = text[max(0, start - radius) : start]
        after = text[end : min(len(text), end + radius)]
        return SpellEngine._clean_context(before), SpellEngine._clean_context(after)

    @staticmethod
    def _clean_context(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def add_word(self, word: str) -> str | None:
        normalized = self._normalize_word(word)
        if not normalized:
            return None

        self.sym_spell.create_dictionary_entry(normalized, 100)
        existing_words = set(self._read_user_words())
        if normalized not in existing_words:
            existing_words.add(normalized)
            self.user_words_path.write_text("\n".join(sorted(existing_words)) + "\n", encoding="utf-8")
        return normalized

    def _load_user_words(self) -> None:
        self._load_words(self._read_user_words())

    def _read_user_words(self) -> list[str]:
        if not self.user_words_path.exists():
            return []
        words = []
        for line in self.user_words_path.read_text(encoding="utf-8").splitlines():
            normalized = self._normalize_word(line)
            if normalized:
                words.append(normalized)
        return words

    @staticmethod
    def _normalize_word(word: str) -> str:
        return word.strip().strip("'").lower()
