#!/usr/bin/env python3
"""
Lightweight Static Code & Secret Security Scanner
Detects potential credential leaks, injection vectors, and dangerous patterns.
"""
import os
import re
import argparse

RULES = [
    {
        "id": "SEC-001",
        "severity": "CRITICAL",
        "desc": "Possible hardcoded API key or private secret",
        "pattern": r'(?i)(api[_-]?key|secret|token|password|auth_token)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']'
    },
    {
        "id": "SEC-002",
        "severity": "HIGH",
        "desc": "Potential command injection (shell=True or system invocation)",
        "pattern": r'(subprocess\.(Popen|call|run|check_output)\(.*shell\s*=\s*True|os\.system\(|os\.popen\()'
    },
    {
        "id": "SEC-003",
        "severity": "HIGH",
        "desc": "Insecure string formatting in SQL statement",
        "pattern": r'(?i)(execute|cursor\.execute)\s*\(\s*f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)'
    },
    {
        "id": "SEC-004",
        "severity": "MEDIUM",
        "desc": "Insecure deserialization (eval, pickle.loads without verification)",
        "pattern": r'\b(eval\(|pickle\.loads?\()'
    }
]

IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}

def scan_file(filepath):
    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                for rule in RULES:
                    if re.search(rule["pattern"], line):
                        findings.append({
                            "rule_id": rule["id"],
                            "severity": rule["severity"],
                            "desc": rule["desc"],
                            "file": filepath,
                            "line": line_no,
                            "snippet": line.strip()
                        })
    except Exception as e:
        pass
    return findings

def scan_directory(target_dir):
    print(f"[cybersecurity-audit] Scanning directory '{target_dir}'...")
    all_findings = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith((".py", ".js", ".ts", ".go", ".env", ".sh", ".json")):
                path = os.path.join(root, file)
                all_findings.extend(scan_file(path))

    if not all_findings:
        print("[cybersecurity-audit] No security issues detected! Repository clean.")
        return 0

    print(f"\n[cybersecurity-audit] Found {len(all_findings)} security findings:\n")
    for f in all_findings:
        print(f"[{f['severity']}] {f['rule_id']} in {f['file']}:{f['line']}")
        print(f"  Description: {f['desc']}")
        print(f"  Snippet: {f['snippet']}\n")
    return len(all_findings)

def main():
    parser = argparse.ArgumentParser(description="Scan codebase for security anti-patterns")
    parser.add_argument("--target", default=".", help="Path to file or folder to scan")
    args = parser.parse_args()
    scan_directory(args.target)

if __name__ == "__main__":
    main()
