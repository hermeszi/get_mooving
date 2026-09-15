"""
Makes src/*.py importable as top-level modules (e.g. `import planner`)
without turning src/ into a package — every script there already uses
flat imports like `from onemap import search_location`, so tests do
the same rather than introducing a different import style just for
tests/.
"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))
