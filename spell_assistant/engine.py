from __future__ import annotations

import re
from pathlib import Path
import os
import symspellpy

from symspellpy import SymSpell, Verbosity

from spell_assistant.config import DEFAULT_KNOWN_WORDS, USER_WORDS_FILE, USER_BIGRAMS_FILE
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

FORCE_CONTRACTION_CHECK = {
    "cant", "wont", "dont", "isnt", "arent", "wasnt", "werent", 
    "havent", "hasnt", "hadnt", "wouldnt", "couldnt", "shouldnt", 
    "doesnt", "didnt", "theyre", "youre", "weve", "thats", "whats", 
    "heres", "theres", "wheres", "lets"
}

class SpellEngine:
    def __init__(self, user_words_path: Path = USER_WORDS_FILE, user_bigrams_path: Path = USER_BIGRAMS_FILE, extra_known_words: list[str] | None = None) -> None:
        self.sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        self.user_words_path = user_words_path
        self.user_bigrams_path = user_bigrams_path
        
        base_dir = os.path.dirname(symspellpy.__file__)
        dictionary_path = os.path.join(base_dir, "frequency_dictionary_en_82_765.txt")
        bigram_path = os.path.join(base_dir, "frequency_bigramdictionary_en_243_342.txt")
        
        self.sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
        self.sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)
        
        # Boost common contractions so they are suggested over obscure words
        common_contractions = [
            "don't", "can't", "won't", "didn't", "doesn't", "isn't", "aren't", 
            "wasn't", "weren't", "haven't", "hasn't", "hadn't", "wouldn't", 
            "couldn't", "shouldn't", "they're", "we're", "you're", "it's", 
            "that's", "what's", "where's", "there's", "let's", "he's", "she's",
            "i'll", "you'll", "they'll", "we'll", "i've", "you've", "they've", 
            "we've", "i'd", "you'd", "they'd", "we'd"
        ]
        for c in common_contractions:
            self.sym_spell.create_dictionary_entry(c, 1_000_000_000)
        
        self._load_words(DEFAULT_KNOWN_WORDS)
        if extra_known_words:
            self._load_words(extra_known_words)
        self._load_user_words()
        self._load_user_bigrams()

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

            if normalized in FORCE_CONTRACTION_CHECK:
                is_known = False

            if not is_known:
                context_before, context_after = self._context(text, match.start(), match.end())
                suggestions = self._suggestions(word, context_before, context_after)
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

    def _grammar_penalty(self, term: str, prev_word: str, next_word: str) -> int:
        penalty = 0
        pronouns = {"it", "he", "she", "they", "we", "i", "you", "me", "him", "her", "us", "them"}
        articles = {"a", "an", "the"}
        prepositions = {"to", "in", "on", "at", "with", "by", "for", "of", "about", "as"}
        
        # Rule 1: 'to it an' -> preposition + pronoun + article is usually invalid
        if prev_word in prepositions and term in pronouns and next_word in articles:
            penalty += 10**20
            
        # Rule 2: pronoun + article is generally invalid ('it an', 'he the')
        if term in pronouns and next_word in articles:
            penalty += 10**20
            
        return penalty

    def _suggestions(self, word: str, context_before: str, context_after: str) -> list[str]:
        normalized = self._normalize_word(word)
        suggestions = self.sym_spell.lookup(normalized, Verbosity.ALL, max_edit_distance=2)
        compound = self.sym_spell.lookup_compound(normalized, max_edit_distance=2)
        compound_term = compound[0].term if compound else None

        prev_word = ""
        if context_before:
            words = re.findall(r"[A-Za-z]+", context_before)
            if words: prev_word = words[-1].lower()
            
        next_word = ""
        if context_after:
            words = re.findall(r"[A-Za-z]+", context_after)
            if words: next_word = words[0].lower()

        scored = []
        for s in suggestions:
            score = s.count
            
            bigram_count = 0
            if prev_word:
                bigram = f"{prev_word} {s.term}"
                if bigram in self.sym_spell.bigrams:
                    bigram_count += self.sym_spell.bigrams[bigram]
            if next_word:
                bigram = f"{s.term} {next_word}"
                if bigram in self.sym_spell.bigrams:
                    bigram_count += self.sym_spell.bigrams[bigram]
                    
            final_score = (score + (bigram_count * 10_000_000)) / (100 ** s.distance)
            
            # Massive boost if the suggestion is just the original word with an apostrophe added
            if s.term.replace("'", "") == normalized and "'" in s.term:
                final_score += 10**20
                
            # Apply grammar penalties to prevent mathematically probable but grammatically impossible phrases
            final_score -= self._grammar_penalty(s.term, prev_word, next_word)
                
            scored.append((final_score, s.term))
            
        if compound_term and " " in compound_term:
            scored.append((10**15, compound_term))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        
        seen = set()
        final_suggestions = []
        for _, term in scored:
            if term not in seen:
                seen.add(term)
                final_suggestions.append(term)
                
        return final_suggestions[:5]

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

    def _load_user_bigrams(self) -> None:
        if not self.user_bigrams_path.exists():
            return
        try:
            for line in self.user_bigrams_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                parts = line.rsplit(" ", 1)
                if len(parts) == 2:
                    bigram = parts[0]
                    try:
                        count = int(parts[1])
                        # Massively boost user bigrams
                        self.sym_spell.bigrams[bigram] = self.sym_spell.bigrams.get(bigram, 0) + (count * 1_000_000)
                    except ValueError:
                        pass
        except Exception:
            pass

    def learn_from_text(self, text: str) -> None:
        """Parses final text, extracts bigrams, and saves them to user bigrams to learn user's style."""
        words = [self._normalize_word(w) for w in re.findall(r"[A-Za-z']+", text) if self._normalize_word(w)]
        if len(words) < 2:
            return

        # Count new bigrams
        new_counts = {}
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            new_counts[bigram] = new_counts.get(bigram, 0) + 1

        # Read existing
        existing_counts = {}
        if self.user_bigrams_path.exists():
            try:
                for line in self.user_bigrams_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    parts = line.rsplit(" ", 1)
                    if len(parts) == 2:
                        existing_counts[parts[0]] = int(parts[1])
            except Exception:
                pass

        # Merge
        for bg, count in new_counts.items():
            existing_counts[bg] = existing_counts.get(bg, 0) + count
            # Update live engine too!
            self.sym_spell.bigrams[bg] = self.sym_spell.bigrams.get(bg, 0) + (count * 1_000_000)

        # Save back
        lines = [f"{bg} {count}" for bg, count in existing_counts.items()]
        try:
            self.user_bigrams_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _normalize_word(word: str) -> str:
        return word.strip().strip("'").lower()
