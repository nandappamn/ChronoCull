---
name: openviking-context
description: >-
  Manage massive codebase and document context using a virtual filesystem paradigm (viking://)
  with tiered L0/L1/L2 loading. Use this skill when dealing with large repositories, extensive
  documentation, or complex project structures where loading entire files causes token bloat.
---

# OpenViking Context Skill

Inspired by [`volcengine/OpenViking`](https://github.com/volcengine/OpenViking), this skill equips the agent to manage context as an organized, hierarchical virtual filesystem rather than flat vector search chunks.

## The Core Concept: Context as a Filesystem

In large projects, dumping thousands of lines into the LLM context causes distraction, degraded reasoning, and high token costs. OpenViking uses **Tiered Progressive Disclosure**:

```
[L0: Meta-Overview]  ──>  [L1: Structural Directory]  ──>  [L2: Deep Chunk Inspection]
  ~50-100 tokens            ~500 tokens                     Targeted code / text only
```

- **L0 (Index/Signatures)**: Brief name, summary, and interface signatures.
- **L1 (Structural Layout)**: Directory listing, module dependencies, and entry-points.
- **L2 (Deep Content)**: Targeted byte or line ranges read only on demand.

---

## When to Use

- When exploring an unfamiliar repository with hundreds of files.
- When querying large API documentation or specifications.
- When searching for specific function implementations across nested directories.
- To avoid blowing through context window token limits.

---

## Tool Usage Commands

Use the local `viking_fs.py` script for progressive context exploration:

### 1. L0 Overview (Fast Metadata & Table of Contents)
```bash
python .agents/skills/openviking-context/scripts/viking_fs.py tree --depth 2
```

### 2. L1 Directory & Symbol Summary
```bash
python .agents/skills/openviking-context/scripts/viking_fs.py summarize --path src/
```

### 3. L2 Targeted Chunk Inspection (Grep & Chunk Read)
```bash
# Grep across context without dumping entire files
python .agents/skills/openviking-context/scripts/viking_fs.py grep --term "authenticateUser" --path src/
```

---

## Best Practices

1. **Always start at L0**: Never read 20 files at once. Read the directory tree, pinpoint the exact file, then read only the target lines.
2. **Deterministic URIs**: Reference resources using clear path protocols (`viking://path/to/module#function`).
3. **Prune Stale Context**: Discard scratch files and temporary logs when transitioning between task phases.
