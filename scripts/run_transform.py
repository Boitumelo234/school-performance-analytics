"""Temporary runner to avoid PowerShell quoting issues."""

import sys
from pathlib import Path

# Add project root to sys.path so `scripts.transform` can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.transform import main

print("calling main...")
main()
print("main returned.")