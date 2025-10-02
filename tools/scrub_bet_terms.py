#!/usr/bin/env python3
"""
Scrub sportsbook-y phrases from UI strings without breaking code.
- Rewrites ONLY string literals in .py files via AST
- For text files (.md/.html/.txt/.json/.yaml), uses safe regex word-boundary replacements
- Dry-run by default; pass --apply to write changes
"""

from __future__ import annotations
import argparse, ast, re, sys
from pathlib import Path

# --- mappings (case-insensitive) ---
PHRASES = [
    (r"\bbet log\b",              "Calculated Log"),
    (r"\bbet history\b",          "Calculated History"),
    (r"\badd to bet slip\b",      "Calculate This"),
    (r"\bmicro bets\b",           "Micro Calculations"),
]

# Also catch common capitalization variants (optional; handled by IGNORECASE)
FLAGS = re.IGNORECASE

TEXT_EXTS = {".md", ".markdown", ".html", ".htm", ".txt", ".json", ".yaml", ".yml", ".csv"}
PY_EXTS   = {".py"}

def replace_phrases(text: str) -> tuple[str, int]:
    count = 0
    for pat, repl in PHRASES:
        text, n = re.subn(pat, repl, text, flags=FLAGS)
        count += n
    return text, count

class StringRewriter(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str):
            new_s, n = replace_phrases(node.value)
            if n:
                return ast.Constant(value=new_s)
        return node

def process_py(path: Path, apply: bool) -> int:
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # fallback to text replacement if parse fails
        new_src, n = replace_phrases(src)
        if apply and n:
            path.write_text(new_src, encoding="utf-8")
        return n
    rewriter = StringRewriter()
    new_tree = rewriter.visit(tree)
    ast.fix_missing_locations(new_tree)
    new_src = src
    try:
        new_src = ast.unparse(new_tree)  # py3.9+
    except Exception:
        # If unparse unavailable/failed, do a text fallback on whole file as last resort
        new_src, n = replace_phrases(src)
        if apply and n:
            path.write_text(new_src, encoding="utf-8")
        return n
    # Count changes by comparing string replacement directly too
    _, n = replace_phrases(src)
    if apply and n and new_src != src:
        path.write_text(new_src, encoding="utf-8")
    return n

def process_text(path: Path, apply: bool) -> int:
    src = path.read_text(encoding="utf-8", errors="ignore")
    new_src, n = replace_phrases(src)
    if apply and n:
        path.write_text(new_src, encoding="utf-8")
    return n

def should_skip(path: Path) -> bool:
    # Skip virtual envs, git, data dumps, models, migrations, and node_modules
    bad = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".mypy_cache"}
    parts = set(p.name for p in path.parents)
    return bool(parts & bad)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Project root (default: .)")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    changed_total = 0
    files_total = 0

    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        ext = path.suffix.lower()
        if ext in PY_EXTS:
            n = process_py(path, args.apply)
        elif ext in TEXT_EXTS:
            n = process_text(path, args.apply)
        else:
            continue
        files_total += 1
        changed_total += n
        if n:
            action = "APPLY" if args.apply else "DRY"
            print(f"[{action}] {n:>2} change(s) in {path.relative_to(root)}")

    print(f"\nScanned {files_total} files. {'WROTE' if args.apply else 'DRY-RUN'} changes:", changed_total)

if __name__ == "__main__":
    sys.exit(main())
