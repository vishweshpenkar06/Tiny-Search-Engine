import logging
import sys

def setup_logger():
    """Configure basic logging for the application."""
    logger = logging.getLogger('search_engine')
    logger.setLevel(logging.INFO)
    
    # Create console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(ch)
        
    return logger

logger = setup_logger()
