#!/usr/bin/env python3
"""
Harness Verification Utility
Checks agent environment sanity, tests, and syntax constraints.
"""
import os
import sys
import subprocess
import argparse

def check_python_syntax():
    print("[harness] Checking Python syntax across repository...")
    errors = 0
    for root, _, files in os.walk("."):
        if any(ignored in root for ignored in [".git", ".venv", "venv", "node_modules"]):
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                res = subprocess.run([sys.executable, "-m", "py_compile", path], capture_output=True, text=True)
                if res.returncode != 0:
                    print(f"  ❌ Syntax error in {path}:\n{res.stderr.strip()}")
                    errors += 1
    if errors == 0:
        print("  ✅ All Python files passed syntax check.")
    return errors

def check_agent_skills_structure():
    print("[harness] Checking .agents/skills/ directory structure...")
    skills_dir = os.path.join(".agents", "skills")
    if not os.path.exists(skills_dir):
        print("  ❌ Missing .agents/skills directory.")
        return 1
    
    missing_skills = 0
    for skill_name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, skill_name)
        if os.path.isdir(skill_path):
            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.exists(skill_md):
                print(f"  ❌ Skill '{skill_name}' is missing SKILL.md")
                missing_skills += 1
            else:
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not (content.startswith("---") and "name:" in content and "description:" in content):
                        print(f"  ⚠️ Skill '{skill_name}/SKILL.md' may have invalid YAML frontmatter.")
                    else:
                        print(f"  ✅ Skill '{skill_name}' valid.")
    return missing_skills

def check_agents_specification():
    print("[harness] Checking AGENTS.md master specification and core principles...")
    agents_file = "AGENTS.md"
    if not os.path.exists(agents_file):
        print("  ❌ Missing AGENTS.md in repository root.")
        return 1
    
    with open(agents_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    required_sections = [
        "Think Before Coding",
        "Simplicity First",
        "Surgical Changes",
        "Goal-Driven Execution",
        "Master 4-Phase Workflow Protocol"
    ]
    
    missing = [sec for sec in required_sections if sec not in content]
    if missing:
        print(f"  ❌ AGENTS.md missing required sections: {missing}")
        return len(missing)
    
    print("  ✅ AGENTS.md contains all core Karpathy disciplines and workflow protocols.")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Verify Harness and Agent Constraints")
    parser.add_argument("--check-all", action="store_true", default=True, help="Run all verification checks")
    args = parser.parse_args()

    print("=== Agent Harness Verification ===")
    err1 = check_python_syntax()
    err2 = check_agent_skills_structure()
    err3 = check_agents_specification()
    
    total = err1 + err2 + err3
    print(f"\nVerification finished with {total} issue(s).")
    sys.exit(0 if total == 0 else 1)

if __name__ == "__main__":
    main()
