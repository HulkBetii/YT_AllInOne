#!/usr/bin/env python3
"""
Simple entry point for YouTube All-in-One CLI
"""

import sys
import os

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the CLI app
from src.app_cli import app

if __name__ == "__main__":
    app()
