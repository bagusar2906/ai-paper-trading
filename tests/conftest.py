import sys
from pathlib import Path

# Ensure the project root (parent of this tests/ folder, which contains the
# `app` package) is importable regardless of what directory pytest is
# invoked from.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
