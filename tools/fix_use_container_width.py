# tools/fix_use_container_width.py
from __future__ import annotations
import ast, os, shutil
from pathlib import Path

ROOT = Path(r"C:\Projects\edge-finder")  # <- change if needed
TARGET_DIRS = [
    ROOT / "serving_ui" / "app" / "pages",
    ROOT / "serving_ui" / "app",          # include app root files too (optional)
]

class UCWTransformer(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        # Find existing keywords
        kw_names = [k.arg for k in node.keywords if k.arg is not None]
        has_width = "width" in kw_names

        new_keywords = []
        pending_width = None  # ('stretch' | 'content') to add if needed

        for k in node.keywords:
            if k.arg == "use_container_width":
                # Decide replacement
                val = None
                if isinstance(k.value, ast.Constant) and isinstance(k.value.value, bool):
                    val = "stretch" if k.value.value else "content"
                # If dynamic (non-literal) -> choose stretch by default
                if val is None:
                    val = "stretch"
                if has_width:
                    # Width already present: just drop use_container_width
                    continue
                else:
                    # Keep place; we’ll add width here instead
                    pending_width = ast.keyword(arg="width", value=ast.Constant(val))
                    continue
            new_keywords.append(k)

        if pending_width is not None:
            new_keywords.append(pending_width)

        node.keywords = new_keywords
        return node

def process_file(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False  # skip unparseable files

    new_tree = UCWTransformer().visit(tree)
    ast.fix_missing_locations(new_tree)

    try:
        new_src = ast.unparse(new_tree)  # py>=3.9
    except Exception:
        # Fallback: don't modify if unparse fails
        return False

    if new_src != src:
        # backup once
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(path, bak)
        path.write_text(new_src, encoding="utf-8")
        return True
    return False

def main():
    changed = 0
    scanned = 0
    for base in TARGET_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            scanned += 1
            if process_file(p):
                changed += 1
                print(f"[fixed] {p}")
    print(f"\nDone. Scanned {scanned} files, modified {changed}.")

if __name__ == "__main__":
    main()
