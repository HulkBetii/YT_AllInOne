#!/usr/bin/env python3
"""Text utility functions for the YouTube All-in-One app"""

import re
from typing import Optional


def clean_ansi_codes(text: str) -> str:
    """
    Remove ANSI escape codes from text to make it safe for GUI display.
    
    Args:
        text: Text that may contain ANSI escape codes
        
    Returns:
        Clean text without ANSI codes
    """
    if not text:
        return text
    
    # Remove standard ANSI escape sequences
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    
    # Remove common color codes like [0;31m, [0m, etc.
    text = re.sub(r'\[0;\d+m', '', text)
    text = re.sub(r'\[\d+m', '', text)
    
    # Remove any remaining control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    return text.strip()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_error_message(error: str, max_length: Optional[int] = None) -> str:
    """
    Format error message for display by cleaning ANSI codes and optionally truncating.
    
    Args:
        error: Raw error message
        max_length: Optional maximum length for truncation
        
    Returns:
        Formatted error message safe for GUI display
    """
    cleaned = clean_ansi_codes(error)
    
    if max_length:
        cleaned = truncate_text(cleaned, max_length)
    
    return cleaned
