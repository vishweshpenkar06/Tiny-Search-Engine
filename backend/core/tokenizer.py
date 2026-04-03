import re
from typing import List, Set

class Tokenizer:
    """Handles tokenization and text preprocessing for the search engine."""
    
    def __init__(self):
        # A comprehensive set of English stop words
        self.stop_words: Set[str] = {
            'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and',
            'any', 'are', 'aren\'t', 'as', 'at', 'be', 'because', 'been', 'before', 'being',
            'below', 'between', 'both', 'but', 'by', 'can\'t', 'cannot', 'could', 'couldn\'t',
            'did', 'didn\'t', 'do', 'does', 'doesn\'t', 'doing', 'don\'t', 'down', 'during',
            'each', 'few', 'for', 'from', 'further', 'had', 'hadn\'t', 'has', 'hasn\'t', 'have',
            'haven\'t', 'having', 'he', 'he\'d', 'he\'ll', 'he\'s', 'her', 'here', 'here\'s',
            'hers', 'herself', 'him', 'himself', 'his', 'how', 'how\'s', 'i', 'i\'d', 'i\'ll',
            'i\'m', 'i\'ve', 'if', 'in', 'into', 'is', 'isn\'t', 'it', 'it\'s', 'its', 'itself',
            'let\'s', 'me', 'more', 'most', 'mustn\'t', 'my', 'myself', 'no', 'nor', 'not',
            'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours',
            'ourselves', 'out', 'over', 'own', 'same', 'shan\'t', 'she', 'she\'d', 'she\'ll',
            'she\'s', 'should', 'shouldn\'t', 'so', 'some', 'such', 'than', 'that', 'that\'s',
            'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'there\'s',
            'these', 'they', 'they\'d', 'they\'ll', 'they\'re', 'they\'ve', 'this', 'those',
            'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasn\'t', 'we',
            'we\'d', 'we\'ll', 'we\'re', 'we\'ve', 'were', 'weren\'t', 'what', 'what\'s',
            'when', 'when\'s', 'where', 'where\'s', 'which', 'while', 'who', 'who\'s', 'whom',
            'why', 'why\'s', 'with', 'won\'t', 'would', 'wouldn\'t', 'you', 'you\'d', 'you\'ll',
            'you\'re', 'you\'ve', 'your', 'yours', 'yourself', 'yourselves'
        }

    def tokenize(self, text: str) -> List[str]:
        """
        Convert text to tokens.
        
        Process:
        1. Convert to lowercase
        2. Remove punctuation and extract word characters
        3. Remove stop words
        4. Remove single character tokens
        """
        # Convert to lowercase
        text = str(text).lower()
        
        # Replace non-alphanumeric characters with spaces to preserve word boundaries
        # This is better than just finding word chars as it handles some edge cases better
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split into tokens (find all consecutive Word characters)
        # Using \b\w+\b finds word boundaries and word characters
        # Using a simpler split to handle words with numbers correctly
        raw_tokens = text.split()
        
        # Filter stop words and single-character words (except numbers if needed, but here we just filter length <= 1 unless it's a digit)
        # We might want to keep single digits.
        tokens = []
        for token in raw_tokens:
            if token not in self.stop_words:
                # Keep tokens that are either longer than 1 char, or a single digit
                if len(token) > 1 or token.isdigit():
                    tokens.append(token)
                    
        return tokens
