"""Top-level ASGI Application entrypoint for VAL."""

import sys
from pathlib import Path

# Add backend and project root to Python search path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from val.api.app import app
