from typing import List, Set

from core.analysis import STOP_WORDS, Analyzer


class Tokenizer:
    def __init__(self, config=None, synonyms=None):
        self.analyzer = Analyzer(config, synonyms)
        self.stop_words: Set[str] = set(STOP_WORDS)

    def tokenize(self, text: str) -> List[str]:
        return [token.term for token in self.analyzer.analyze(text, "body")]

    def analyze(self, text: str, field: str = "body"):
        return self.analyzer.analyze(text, field)
