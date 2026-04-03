import re
from typing import Dict, Any, Tuple

def validate_search_query(query: str) -> Tuple[bool, str, str]:
    """
    Validate and sanitize a search query.
    Returns: (is_valid, error_message, sanitized_query)
    """
    if not query or not isinstance(query, str):
        return False, "Query cannot be empty.", ""
        
    query = query.strip()
    
    if len(query) == 0:
        return False, "Query cannot be empty.", ""
        
    if len(query) > 200:
        return False, "Query is too long (maximum 200 characters).", ""
        
    # Basic sanitization: remove HTML/script tags
    sanitized = re.sub(r'<[^>]*>', '', query)
    
    # Check for invalid characters
    # Allow alphanumeric, spaces, hyphens, quotes, and dots
    if not re.match(r'^[a-zA-Z0-9\s\-"\'\.]+$', sanitized):
         return False, "Query contains invalid characters. Only alphanumeric characters, spaces, hyphens, quotes, and dots are allowed.", ""
         
    return True, "", sanitized

def validate_file_upload(filename: str, content_length: int) -> Tuple[bool, str]:
    """Validate uploaded file size and type."""
    MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB
    ALLOWED_EXTENSIONS = {'.txt', '.md', '.html', '.htm', '.csv'}
    
    if not filename:
        return False, "No filename provided."
        
    import os
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
    if content_length > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size is 10MB."
        
    return True, ""
