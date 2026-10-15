#!/usr/bin/env python3
"""
Agent Memory Manager
Lightweight, local-first persistent memory engine for coding agents.
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone

MEMORY_DIR = os.path.join(os.getcwd(), ".agent-memory")

def ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)

def record_memory(category: str, title: str, content: str, tags: list = None):
    ensure_dir()
    filepath = os.path.join(MEMORY_DIR, f"{category}.jsonl")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "title": title,
        "content": content,
        "tags": tags or []
    }
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[agent-memory] Successfully recorded '{title}' in {category}.jsonl")

def search_memory(query: str):
    ensure_dir()
    query_tokens = query.lower().split()
    results = []
    
    for filename in os.listdir(MEMORY_DIR):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(MEMORY_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    text = f"{entry.get('title', '')} {entry.get('content', '')} {' '.join(entry.get('tags', []))}".lower()
                    score = sum(1 for token in query_tokens if token in text)
                    if score > 0:
                        results.append((score, entry))
    
    results.sort(key=lambda x: x[0], reverse=True)
    if not results:
        print(f"[agent-memory] No matching memories found for query: '{query}'")
        return
    
    print(f"[agent-memory] Found {len(results)} memory entries for: '{query}':\n")
    for score, item in results[:10]:
        print(f"[{item['category'].upper()}] {item['title']} ({item['timestamp']})")
        print(f"  {item['content']}")
        if item.get('tags'):
            print(f"  Tags: {', '.join(item['tags'])}")
        print()

def list_memories():
    ensure_dir()
    total = 0
    for filename in sorted(os.listdir(MEMORY_DIR)):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(MEMORY_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
                print(f"- {filename}: {count} entries")
                total += count
    print(f"\nTotal persistent memories: {total}")

def main():
    parser = argparse.ArgumentParser(description="Agent Persistent Memory Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Record
    rec_parser = subparsers.add_parser("record", help="Record a new memory")
    rec_parser.add_argument("--category", choices=["decision", "gotcha", "learning", "preference"], default="learning")
    rec_parser.add_argument("--title", required=True, help="Short summary/title")
    rec_parser.add_argument("--content", required=True, help="Detailed explanation or fix")
    rec_parser.add_argument("--tags", nargs="*", default=[], help="Optional search tags")

    # Search
    search_parser = subparsers.add_parser("search", help="Search persistent memories")
    search_parser.add_argument("--query", required=True, help="Keywords to search for")

    # List
    subparsers.add_parser("list", help="List summary of stored memories")

    args = parser.parse_args()
    if args.command == "record":
        record_memory(args.category, args.title, args.content, args.tags)
    elif args.command == "search":
        search_memory(args.query)
    elif args.command == "list":
        list_memories()

if __name__ == "__main__":
    main()
