import os
from typing import Dict, Any, Optional

class FileParser:
    """Handles reading and extracting text from different file types."""

    @staticmethod
    def parse_file(filepath: str) -> Optional[Dict[str, Any]]:
        """
        Parse a file and return its content and metadata.
        Returns None if file type is unsupported or reading fails.
        """
        if not os.path.isfile(filepath):
            return None

        # Determine file extension
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()

        # Route to appropriate parser
        if ext == '.txt':
            return FileParser._parse_text(filepath)
        elif ext == '.md':
            return FileParser._parse_markdown(filepath)
        elif ext in ['.html', '.htm']:
            return FileParser._parse_html(filepath)
        elif ext == '.csv':
            return FileParser._parse_csv(filepath)
        else:
            print(f"Unsupported file extension: {ext} for {filepath}")
            return None

    @staticmethod
    def _read_file_content(filepath: str) -> Optional[str]:
        """Attempt to read file content using multiple encodings."""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
                return None
                
        # If all fail, try utf-8 with replacement
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            print(f"Final fallback reading failed for {filepath}: {e}")
            return None

    @staticmethod
    def _parse_text(filepath: str) -> Optional[Dict[str, Any]]:
        """Parse plain text files."""
        content = FileParser._read_file_content(filepath)
        if content is None:
            return None
            
        return {
            'content': content,
            'type': 'text/plain'
        }

    @staticmethod
    def _parse_markdown(filepath: str) -> Optional[Dict[str, Any]]:
        """Parse markdown files. (For phase 1, treating mostly as text)"""
        content = FileParser._read_file_content(filepath)
        if content is None:
            return None
            
        # Basic markdown stripping could happen here, 
        # but TF-IDF often benefits from headers/bold words
        # So we just extract the text for now.
        return {
            'content': content,
            'type': 'text/markdown'
        }

    @staticmethod
    def _parse_html(filepath: str) -> Optional[Dict[str, Any]]:
        """Parse HTML files. Strips tags to extract text."""
        content = FileParser._read_file_content(filepath)
        if content is None:
            return None
            
        import re
        
        # Very basic HTML tag stripping (a real app would use BeautifulSoup)
        # Remove script and style elements entirely
        text = re.sub(r'<script.*?</script>', ' ', content, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<style.*?</style>', ' ', text, flags=re.IGNORECASE | re.DOTALL)
        # Remove all other tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode common entities
        text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        # Condense whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return {
            'content': text,
            'type': 'text/html'
        }
        
    @staticmethod
    def _parse_csv(filepath: str) -> Optional[Dict[str, Any]]:
         """Parse CSV files."""
         content = FileParser._read_file_content(filepath)
         if content is None:
             return None
             
         # Basic CSV handling - just treat as text where commas are spaces
         text = content.replace(',', ' ')
         
         return {
             'content': text,
             'type': 'text/csv'
         }
