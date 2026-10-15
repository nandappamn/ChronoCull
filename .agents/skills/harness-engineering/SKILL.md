---
name: harness-engineering
description: >-
  Implement production-grade AI agent harness engineering: bounded execution,
  test-before-code verification loops, deterministic state evaluation, and recursive self-correction.
  Use this skill when building complex agentic systems, designing multi-agent workflows,
  or preventing agents from spiraling into hallucinations and loops.
---

# Harness Engineering Skill

Inspired by [`ai-boost/awesome-harness-engineering`](https://github.com/ai-boost/awesome-harness-engineering) and the core philosophy established in `AGENTS.md`:
$$\text{Agent} = \text{Model} + \text{Harness} + \text{Discipline}$$

While frontier models supply raw reasoning, the **harness** enforces boundaries, deterministic verification loops, memory indexing, sandboxing, and graceful recovery. It operationalizes **Andrej Karpathy's Core Disciplines** (Think Before Coding, Simplicity First, Surgical Changes, and Goal-Driven Execution) into concrete runtime constraints.

---

## When to Use

- Designing multi-agent pipelines or sub-agent delegation topologies.
- Implementing closed-loop verification (write test ➔ run test ➔ modify code ➔ verify pass).
- Debugging agent stall states, tool loops, or context thrashing.
- Enforcing sandboxed execution and least-privilege tool usage.
- Preventing speculative code bloat and unverified code generation.

---

## The 5 Pillars of Harness Engineering

```
┌────────────────────────────────────────────────────────┐
│                      Agent Harness                     │
├─────────────┬─────────────┬─────────────┬──────────────┤
│ 1. Context  │ 2. Tool     │ 3. Eval     │ 4. Safety &  │
│ Bounding    │ Contract    │ Loop        │ Recovery     │
└─────────────┴─────────────┴─────────────┴──────────────┘
```

1. **Context Bounding**:
   - Never inject megabytes of unparsed documentation into prompts.
   - Use tiered indexing: pass high-level signatures first, expand on demand.
2. **Deterministic Tool Contracts**:
   - Tools must return typed, parseable schemas (JSON or structured stdout).
   - Tools should emit explicit error messages with actionable remedy hints.
3. **Continuous Evaluation Loop**:
   - Require automated test suites (`pytest`, `jest`) to validate every modification.
   - Never consider a feature "complete" until an automated verification passes.
4. **Error Budgets & Loop Termination**:
   - Cap consecutive tool failures at a fixed threshold (e.g. 3 attempts).
   - If an agent fails the same step 3 times, pause and request human feedback rather than spiraling.
5. **Sandboxed Isolation**:
   - Run untrusted generated code inside containerized or sandbox boundaries.

---

## Harness Verification Script

Use `scripts/verify_harness.py` to evaluate whether code changes comply with testing and linting constraints:

```bash
# Verify harness integrity and test pass rate
python .agents/skills/harness-engineering/scripts/verify_harness.py --check-all
```
