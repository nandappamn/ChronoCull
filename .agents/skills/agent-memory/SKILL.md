---
name: agent-memory
description: >-
  Manage persistent long-term memory, session state, architectural decisions,
  and cross-task learnings for AI coding agents. Use this skill when the agent needs
  to remember project context, recall past fixes, search past decisions, or log new learnings.
---

# Agent Memory Skill

This skill equips the agent with persistent long-term memory across sessions, inspired by [`rohitg00/agentmemory`](https://github.com/rohitg00/agentmemory) and local-first memory systems. It prevents agents from resetting to zero context between conversations.

## When to Use

- At the start of a task: Query memory to recall user preferences, architectural rules, past bug fixes, and project-specific quirks.
- During execution: Check if an encountered error or pattern was already solved in a previous session.
- At the end of a task: Persist key decisions, newly created conventions, or lessons learned into the local knowledge store.

---

## Memory Store Architecture

Memory is maintained locally in `.agent-memory/` at the repository root:
- `.agent-memory/decision.jsonl`: Architectural and design choices.
- `.agent-memory/gotcha.jsonl`: Bug fixes, environment quirks, and syntax traps.
- `.agent-memory/preferences.json`: User and project conventions.

---

## Usage Commands

Use the built-in memory helper script located at `scripts/memory_manager.py`:

### 1. Recall / Search Memories
```bash
# Search for relevant memories before beginning a task
python .agents/skills/agent-memory/scripts/memory_manager.py search --query "authentication database schema"
```

### 2. Record a New Architectural Decision
```bash
# Save an important design decision
python .agents/skills/agent-memory/scripts/memory_manager.py record \
  --category decision \
  --title "Adopt PostgreSQL for JSONB storage" \
  --content "Chose PostgreSQL over MongoDB due to relational consistency requirements and JSONB indexing capability."
```

### 3. Record a Gotcha or Bug Fix
```bash
# Save a debugging lesson learned
python .agents/skills/agent-memory/scripts/memory_manager.py record \
  --category gotcha \
  --title "Playwright headless flag on Linux" \
  --content "Requires --no-sandbox and --disable-dev-shm-usage when running inside minimal Docker containers."
```

### 4. List All Stored Learnings
```bash
python .agents/skills/agent-memory/scripts/memory_manager.py list
```

---

## Best Practices

1. **Be Concise**: Store core rationales, not raw chat transcripts.
2. **Tag Metadata**: Include files or components affected to improve search recall.
3. **Keep Local-First**: Avoid transmitting memory stores to external unauthenticated endpoints.
