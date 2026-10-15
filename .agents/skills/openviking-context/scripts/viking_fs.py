#!/usr/bin/env python3
"""
OpenViking Context Navigator (viking_fs)
Provides tiered L0 (tree), L1 (symbol summary), and L2 (grep/chunk) context inspection.
"""
import os
import sys
import re
import argparse

IGNORE = {".git", ".venv", "venv", "node_modules", "__pycache__", ".agent-memory"}

def l0_tree(start_path: str = ".", max_depth: int = 2, current_depth: int = 0):
    if current_depth > max_depth:
        return
    prefix = "  " * current_depth
    try:
        entries = sorted(os.listdir(start_path))
    except Exception as e:
        return
    for entry in entries:
        if entry in IGNORE:
            continue
        full_path = os.path.join(start_path, entry)
        if os.path.isdir(full_path):
            print(f"{prefix}📁 {entry}/")
            l0_tree(full_path, max_depth, current_depth + 1)
        else:
            size_kb = round(os.path.getsize(full_path) / 1024, 1)
            print(f"{prefix}📄 {entry} ({size_kb} KB)")

def l1_summarize(target_path: str):
    print(f"[openviking-context:L1] Summarizing symbols in: '{target_path}'")
    if os.path.isfile(target_path):
        files = [target_path]
    else:
        files = []
        for root, dirs, filenames in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE]
            for f in filenames:
                if f.endswith((".py", ".js", ".ts", ".go")):
                    files.append(os.path.join(root, f))

    for fpath in files:
        print(f"\n🔹 {fpath}:")
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                # match def, class, interface, export function
                if re.match(r'^\s*(def|class|interface|type|async def|export\s+(function|class|interface))\s+([A-Za-z0-9_]+)', line):
                    print(f"  Line {line_no:4d}: {line.strip()[:100]}")

def l2_grep(term: str, target_path: str = "."):
    print(f"[openviking-context:L2] Grepping for '{term}' in '{target_path}'...")
    matches = 0
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in IGNORE]
        for file in files:
            fpath = os.path.join(root, file)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if term.lower() in line.lower():
                            matches += 1
                            print(f"{fpath}:{line_no}: {line.strip()[:120]}")
            except Exception:
                pass
    print(f"\n[openviking-context] Found {matches} match(es).")

def main():
    parser = argparse.ArgumentParser(description="OpenViking Context Navigator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # L0 tree
    tree_p = subparsers.add_parser("tree", help="L0: Directory tree overview")
    tree_p.add_argument("--depth", type=int, default=2, help="Max recursion depth")
    tree_p.add_argument("--path", default=".", help="Starting path")

    # L1 summarize
    sum_p = subparsers.add_parser("summarize", help="L1: Structural symbol summary")
    sum_p.add_argument("--path", default=".", help="Target file or directory")

    # L2 grep
    grep_p = subparsers.add_parser("grep", help="L2: Targeted search across context")
    grep_p.add_argument("--term", required=True, help="Search string")
    grep_p.add_argument("--path", default=".", help="Target path")

    args = parser.parse_args()
    if args.command == "tree":
        print(f"[openviking-context:L0] Context Hierarchy Tree:")
        l0_tree(args.path, args.depth)
    elif args.command == "summarize":
        l1_summarize(args.path)
    elif args.command == "grep":
        l2_grep(args.term, args.path)

if __name__ == "__main__":
    main()
