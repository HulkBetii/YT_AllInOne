#!/usr/bin/env python3
"""
Simple entry point for YouTube All-in-One GUI
"""

import sys
import os

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the GUI app
from src.app_gui import main

if __name__ == "__main__":
    sys.exit(main())
