from pathlib import Path
import sys
_here = Path(__file__).resolve()
serving_ui = _here.parent.parent  # .../serving_ui
p = str(serving_ui)
if p not in sys.path:
    sys.path.insert(0, p)
