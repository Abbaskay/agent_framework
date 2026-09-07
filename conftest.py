"""Pytest configuration — puts the project root on sys.path.

Lets tests use the same absolute imports the application does (`from core...`)
without requiring the package to be installed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
