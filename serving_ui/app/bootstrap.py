from pathlib import Path
import sys

def bootstrap_paths():
    app_dir = Path(__file__).resolve().parent
    root = app_dir.parents[2]
    su = str(app_dir.parent)
    rt = str(root)
    for p in (su, rt):
        if p not in sys.path:
            sys.path.insert(0, p)
    return root