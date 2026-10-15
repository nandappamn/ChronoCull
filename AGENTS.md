# AGENTS.md — ChronoCull Master Agent Specification & Operating Principles

Welcome to the **ChronoCull Media Curation Engine**. This repository combines an intelligent, offline-first photo/video curation pipeline with **Andrej Karpathy's Disciplined Agent Principles** to eliminate common LLM coding pitfalls: wrong assumptions, bloated abstractions, drive-by refactorings, and unverified regressions.

---

## 1. ChronoCull System Context & Core Invariants

**ChronoCull** is an intelligent media curation pipeline that transforms disorganized trip photos and videos into structured, chronologically sorted, geotagged, clustered travelogues, and ready-to-post social media packs.

### Repository & Package Layout
```text
ChronoCull/
├── src/chronocull/
│   ├── cli.py             # CLI commands (--apply, --rollback, --cluster, --export-story, --export-social, --curate-ai)
│   ├── config.py          # Constants, supported file formats, manifest filename & .env loader
│   ├── models.py          # Strongly-typed MediaItem & cluster dataclasses
│   ├── core/
│   │   ├── extractor.py   # 5-tier capture timestamp resolution & EXIF/video atom parsing
│   │   ├── sorter.py      # Chronological ordering, subsecond bursts & collision naming
│   │   ├── renamer.py     # Safe dry-run previews, 2-phase atomic renames & rollback
│   │   ├── clustering.py  # Spatiotemporal clustering (Days/Stops) & GPS interpolation
│   │   ├── social.py      # Zero-copy social staging & caption pack generation
│   │   ├── browser_staging.py # Optional browser-use staging assistant
│   │   ├── manifest.py    # v1 JSON manifest persistence (trip_manifest.json)
│   │   ├── story_manifest.py # v2 Story manifest & GeoJSON route export
│   │   ├── curation.py    # Multimodal AI curation pipeline & TRAVELOGUE.md synthesis
│   │   ├── enricher.py    # Web enrichment client (Google Places)
│   │   ├── vlm_client.py  # Zero-dependency Gemini VLM REST client
│   │   └── html_showcase.py # Responsive editorial HTML photo album generator (travel_album.html)
│   ├── utils/
│   │   ├── geocoder.py    # 100% offline 3D unit-sphere KDTree reverse geocoder
│   │   └── heuristics.py  # 64-bit DCT pHash/dHash, Laplacian blur variance, video CV, color score
│   └── data/
│       └── cities.json.gz # Bundled world cities KDTree dataset
├── tests/                 # Automated pytest suite (13 test modules, 46 unit & integration tests)
├── docs/                  # Architecture blueprints (PLAN.md, FRAMEWORK.md)
├── services/              # Companion microservices (freellm-gateway)
├── .env.example           # Environment variables configuration template
├── .agents/skills/        # Agent skills (harness, memory, context, diagrams, security)
└── .agent-memory/         # Persistent architectural decisions and gotchas
```

### Non-Negotiable Domain Invariants
1. **Safety & Dry-Run by Default**:
   - Never modify, move, or rename files on disk without explicit `--apply`.
   - Dry-run is the default mode. Preview changes using Rich visual tables or JSON output before writing.
2. **Atomic Disk Operations & Staging**:
   - Disk renames must execute in two phases using intermediate UUID staging (`.uuid.tmp`) to prevent collisions, partial state, or overwriting existing files during interruptions.
3. **Rollback & Manifest Fidelity**:
   - Every rename operation must write relative paths (`rel_original_path`, `rel_target_path`) into `trip_manifest.json` so rollback functions reliably across nested subdirectories.
4. **Capture Date Fallback Hierarchy**:
   - Always adhere to the 5-tier fallback order:
     $$\text{Tier 1: EXIF} \longrightarrow \text{Tier 2: QuickTime/MP4 atoms} \longrightarrow \text{Tier 3: Filename Regex} \longrightarrow \text{Tier 4: macOS Spotlight} \longrightarrow \text{Tier 5: Filesystem Stat}$$
5. **Live Photo & Burst Integrity**:
   - Apple Live Photo pairs (`.heic` + `.mov`) must share identical timestamps and base filenames.
   - High-speed bursts must maintain subsecond order via collision counters (`_01`, `_02`).
6. **Offline-First Geocoding**:
   - Geocoding must resolve 100% offline via `scipy.spatial.KDTree` on a 3D unit sphere using `cities.json.gz`. Remote Nominatim lookups are strictly optional, cached, and rate-limited.

---

## 2. Core Operating Philosophy: Agent = Model + Harness + Discipline

$$\text{Agent} = \text{Model} + \text{Harness} + \text{Discipline}$$

Frontier AI models possess strong reasoning capabilities, but naturally suffer from predictable failure modes: making wrong assumptions silently, introducing bloated abstractions, performing drive-by refactorings that break working code, and drifting without clear verification criteria.

In this workspace, an agent does not just emit code. You operate within an engineered harness enforcing four cardinal disciplines:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Karpathy Core Disciplines                         │
├────────────────────┬────────────────────┬──────────────────────────────┤
│ 1. Think Before    │ 2. Simplicity      │ 3. Surgical   │ 4. Goal-     │
│    Coding          │    First           │    Changes    │    Driven    │
└────────────────────┴────────────────────┴───────────────┴──────────────┘
```

---

## 3. The Four Cardinal Principles

### Principle 1: Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before writing or modifying any code:
- **State assumptions explicitly**: Never guess what the user meant. If requirements are underspecified (e.g., media format, scale, performance requirements, boundaries), explicitly list your assumptions before proceeding.
- **Present multiple interpretations**: When ambiguous, lay out the concrete alternatives and ask rather than picking silently.
- **Push back when warranted**: If a simpler, more idiomatic, or less risky approach exists, present it. Do not blindly follow a flawed premise.
- **Stop when confused**: If code or instructions are unclear, stop immediately. Explicitly name what is ambiguous and seek clarification.

### Principle 2: Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

Combat the model's natural bias toward overengineering:
- **Zero speculative features**: Implement only what was explicitly requested. No "future-proofing", speculative utility helpers, or unasked flexibility.
- **No single-use abstractions**: Avoid creating protocols, abstract classes, factories, or wrapper classes for one-time code.
- **No hypothetical error handling**: Do not write defensive handlers for impossible internal states.
- **The Senior Engineer Sniff Test**: Ask yourself: *"Would a senior engineer say this is overcomplicated?"* If 200 lines could be implemented in 50 lines, rewrite it.

### Principle 3: Surgical Changes
**Touch only what you must. Clean up only your own mess.**

Prevent collateral damage and regressions:
- **Zero drive-by refactoring**: Do not reformat adjacent lines, modify untouched comments, alter quoting styles, or reorganize working files outside the task scope.
- **Conform to existing style**: Mirror the codebase's existing conventions (variable naming, typing depth, spacing, error patterns), even if you would personally write it differently.
- **Clean up own orphans**: Remove imports, variables, helpers, or config keys that YOUR changes rendered unused.
- **Preserve pre-existing dead code**: If you encounter pre-existing unused code or technical debt, mention it in your summary—do not unilaterally delete it.
- **The Traceability Test**: Every single line changed in a diff must trace directly to the user's explicit request.

### Principle 4: Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform every task into verifiable, testable success criteria:
- **New Feature** ➔ Write a test or verification script demonstrating the required behavior, then implement until it passes.
- **Bug Fix** ➔ First reproduce the bug with a minimal test or command, identify the root cause, fix it surgically, and verify the test passes.
- **Refactoring** ➔ Ensure existing tests pass before and after the change with zero behavioral regressions.
- **Step-by-Step Verification Loop**: Break multi-step tasks into atomic units:
  ```text
  1. [Step 1] ➔ verify: [command / test / inspect output]
  2. [Step 2] ➔ verify: [command / test / inspect output]
  3. [Step 3] ➔ verify: [command / test / inspect output]
  ```
  Strong criteria allow autonomous execution without thrashing; vague goals ("make it work") guarantee drift.

---

## 4. Pitfall Prevention Matrix

| LLM Failure Mode | Typical Trap Behavior | Karpathy Harness Remedy |
| :--- | :--- | :--- |
| **Wrong Assumptions** | Picks an arbitrary interpretation and writes unwanted code. | **Think Before Coding**: List assumptions up-front; ask before writing code. |
| **Bloated Abstractions** | Builds 500-line class hierarchies for simple logic. | **Simplicity First**: Write the simplest pure function or script that solves the need. |
| **Drive-by Refactoring** | Reformats whitespace, changes quotes, edits unrelated comments. | **Surgical Changes**: Restrict diff to target lines; verify with git diff. |
| **Collateral Breakage** | Deletes or modifies working code it doesn't fully understand. | **Surgical Changes**: Leave unreferenced and legacy blocks untouched. |
| **Vague Execution** | Declares task complete without running tests or inspecting output. | **Goal-Driven Execution**: Closed-loop verification; must show passing test output. |
| **Orphaned Code** | Leaves unused imports or variables created during iteration. | **Surgical Cleanup**: Audit own diffs and prune newly introduced orphans. |

---

## 5. Master 4-Phase Workflow Protocol

When executing any task in this workspace, follow this lifecycle:

```
[Phase 1: Context & Clarify] ➔ [Phase 2: Plan & Verification Contract] ➔ [Phase 3: Surgical Execution] ➔ [Phase 4: Verify & Memory Update]
```

### Phase 1: Context & Clarify (Think Before Coding)
1. **Memory Recall**: Inspect persistent memory (`.agent-memory/decision.jsonl` and `.agent-memory/gotcha.jsonl`) for prior decisions, rules, or environment gotchas.
2. **Context Progressive Disclosure**: Use tiered inspection (L0/L1 via OpenViking) to explore directory structure and signatures before reading full files.
3. **Clarify Ambiguity**: Identify ambiguities, state assumptions, and surface tradeoffs or pushback before executing code.

### Phase 2: Plan & Verification Contract (Goal-Driven)
1. Formulate a concise plan where every step has an explicit verification check:
   ```text
   Step N: <Action> ➔ Verify: <Specific test command or assertion>
   ```
2. Identify relevant workspace skills to invoke.
3. Define the minimal footprint required for the solution.

### Phase 3: Surgical Execution (Simplicity First & Surgical Changes)
1. Apply the simplest possible implementation.
2. Follow existing code idioms and conventions strictly.
3. Keep diffs tightly localized to the requested functionality.
4. Clean up any orphaned imports, variables, or temporary files introduced by the change.

### Phase 4: Verify & Memory Update (Closed-Loop Validation)
1. Execute the verification commands defined in Section 7.
2. Confirm no syntax errors, regressions, or broken contracts exist.
3. Persist notable architectural decisions, discovered quirks, or reusable patterns to `.agent-memory/`.

---

## 6. Workspace Skills Alignment

Skills are organized into primary development harness tools and auxiliary utilities under `.agents/skills/`:

### Core Development & Harness Skills
| Skill | Directory | Primary Purpose |
| :--- | :--- | :--- |
| **Harness Engineering** | `.agents/skills/harness-engineering/` | Bounded execution loops, test-driven validation, syntax check, and error budgets. |
| **Agent Memory** | `.agents/skills/agent-memory/` | Cross-session long-term memory, decision journaling (`decision.jsonl`), and gotcha logging (`gotcha.jsonl`). |
| **OpenViking Context** | `.agents/skills/openviking-context/` | Tiered L0/L1/L2 hierarchical context retrieval and virtual filesystem. |

### Supplemental & Architecture Skills
| Skill | Directory | Primary Purpose |
| :--- | :--- | :--- |
| **Cybersecurity Audit** | `.agents/skills/cybersecurity-audit/` | Static code analysis, secret leak scanning, and path traversal / injection auditing. |
| **Diagram Design** | `.agents/skills/diagram-design/` | Editorial HTML/SVG architectural diagrams and system workflows. |
| **Browser Use** | `.agents/skills/browser-use/` | *Auxiliary*: Web automation (useful if developing future web interfaces). |
| **Scientific Research** | `.agents/skills/scientific-research/` | *Dormant*: Scientific literature retrieval (dormant in media curation context). |

---

## 7. Fast Verification Commands & Tool Conventions

Before completing any task, execute the closed-loop verification suite:

```bash
# 1. Run all unit and integration tests (36 tests, <1s runtime)
pytest

# 2. Run agent harness structural and syntax verification
python3 .agents/skills/harness-engineering/scripts/verify_harness.py

# 3. Test CLI entrypoint sanity
chronocull --help  # Or: PYTHONPATH=src python3 -m chronocull --help
```

### Environment & Tool Conventions
- **Language**: Python 3.10+ (using `.venv` with `pip install -e .`).
- **Dependencies**: Keep dependencies minimal (`Pillow`, `rich`, `numpy`, `scipy`, `pytest`). Do not introduce unprompted third-party packages.
- **Diff Cleanliness**: Before completing a task, inspect diffs to ensure no unintended formatting or whitespace changes were introduced.
