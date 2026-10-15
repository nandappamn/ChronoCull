# AI Agent Skills & Harness Framework

A modular, production-ready framework integrating the 7 foundational paradigms highlighted in **"7 GitHub Repos That Save Months Of AI Work"** with **Andrej Karpathy's Disciplined Agent Operating Principles**:

$$\text{Agent} = \text{Model} + \text{Harness} + \text{Discipline}$$

1. **Browser Use** (`browser-use`) — Autonomous web navigation & form automation.
2. **Agent Memory** (`agent-memory`) — Persistent cross-session knowledge & decision memory.
3. **Scientific Research** (`scientific-research`) — Hypothesis testing & scientific literature retrieval.
4. **Diagram Design** (`diagram-design`) — Editorial, publication-grade HTML & SVG diagrams.
5. **Cybersecurity Audit** (`cybersecurity-audit`) — Automated static analysis, secret scanning, and STRIDE threat modeling.
6. **Harness Engineering** (`harness-engineering`) — Bounded execution loops, test-driven validation, and error budgeting.
7. **OpenViking Context** (`openviking-context`) — Tiered L0/L1/L2 hierarchical context filesystem.

All agent behavior in this workspace is strictly governed by the master specification in **`AGENTS.md`**, enforcing four cardinal disciplines to eliminate common LLM coding pitfalls:
- **Think Before Coding**: Explicit assumptions, ambiguity clarification, tradeoff presentation, and constructive pushback.
- **Simplicity First**: Minimum viable code, no speculative abstractions, no unasked configurability.
- **Surgical Changes**: Zero drive-by refactoring, style conformity, orphan cleanup, direct traceability of diffs.
- **Goal-Driven Execution**: Verifiable success criteria, test-first iteration, and atomic step verification loops (`[Step] ➔ verify: [check]`).

---

## Workspace Structure

```text
chronocull/
├── AGENTS.md                                # Master agent instructions & Karpathy operating principles
├── README.md                                # Repository guide & documentation
├── pyproject.toml                           # PEP 621 packaging & CLI entrypoint
├── requirements.txt                         # Pinned core dependencies
├── .env.example                             # Centralized environment variable template
├── src/chronocull/                           # Core application package
│   ├── cli.py                               # CLI entrypoint (--apply, --cluster, --export-story, etc.)
│   ├── config.py                            # Constants & zero-dependency .env loader
│   ├── models.py                            # MediaItem dataclass
│   ├── core/                                # Processing pipeline
│   │   ├── extractor.py                     # 5-tier metadata parser
│   │   ├── sorter.py                        # Chronological sorting & collision prevention
│   │   ├── renamer.py                       # 2-phase atomic renaming & rollback
│   │   ├── clustering.py                    # Spatiotemporal clustering & GPS interpolation
│   │   ├── manifest.py                      # v1 Manifest persistence (trip_manifest.json)
│   │   ├── story_manifest.py                # v2 Story manifest & GeoJSON route export
│   │   ├── curation.py                      # Multimodal AI curation & TRAVELOGUE.md synthesis
│   │   ├── enricher.py                      # Apify POI web enrichment client
│   │   ├── vlm_client.py                    # Zero-dependency Gemini VLM REST client
│   │   └── html_showcase.py                 # Responsive editorial HTML album generator
│   └── utils/                               # KDTree geocoder & visual heuristics
├── tests/                                   # 36 automated unit & integration tests
├── docs/                                    # Architecture blueprints (PLAN.md, FRAMEWORK.md)
├── services/                                # Companion microservices (freellm-gateway)
├── .agents/
│   └── skills/
│       ├── browser-use/
│       │   ├── SKILL.md                     # Skill instructions & frontmatter
│       │   └── scripts/run_browser_task.py  # Web automation runner
│       ├── agent-memory/
│       │   ├── SKILL.md                     # Persistent memory guidelines
│       │   └── scripts/memory_manager.py    # Local memory CLI (record/search/list)
│       ├── scientific-research/
│       │   ├── SKILL.md                     # Scientific inquiry protocols
│       │   └── scripts/query_pubmed.py      # PubMed / NCBI literature search
│       ├── diagram-design/
│       │   ├── SKILL.md                     # Editorial diagram specifications
│       │   └── resources/template.html      # Responsive HTML/SVG template
│       ├── cybersecurity-audit/
│       │   ├── SKILL.md                     # Defensive security audit workflows
│       │   └── scripts/security_scan.py     # AST & secret leak scanner
│       ├── harness-engineering/
│       │   ├── SKILL.md                     # Harness principles & loop constraints
│       │   └── scripts/verify_harness.py    # Structural integrity & syntax test
│       └── openviking-context/
│           ├── SKILL.md                     # Tiered L0/L1/L2 context protocols
│           └── scripts/viking_fs.py         # Context tree, symbol summary & grep
└── .agent-memory/                           # Persistent architectural decision history
```

---

## Quickstart

### 1. Verify Skills Structure
```bash
python .agents/skills/harness-engineering/scripts/verify_harness.py
```

### 2. Record & Search Memory
```bash
# Record an architectural decision
python .agents/skills/agent-memory/scripts/memory_manager.py record \
  --category decision \
  --title "Use PostgreSQL with JSONB" \
  --content "Adopted PostgreSQL for relational integrity with document store flexibility."

# Search memory
python .agents/skills/agent-memory/scripts/memory_manager.py search --query "PostgreSQL"
```

### 3. Scan for Code Vulnerabilities
```bash
python .agents/skills/cybersecurity-audit/scripts/security_scan.py --target .
```

### 4. Explore Context with OpenViking Tiering
```bash
# L0: Directory overview
python .agents/skills/openviking-context/scripts/viking_fs.py tree --depth 2

# L1: Code symbols summary
python .agents/skills/openviking-context/scripts/viking_fs.py summarize --path .agents/skills/
```

### 5. Media Ingestion, Sorter & Curation Pipeline (`chronocull`)
```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests (36 tests)
pytest

# Preview sorting & renaming plan (Safe Dry-Run)
chronocull /path/to/trip_folder

# Apply renames and generate trip_manifest.json
chronocull /path/to/trip_folder --apply

# Cluster into Days, Stops & Select Burst Heroes
chronocull /path/to/trip_folder --cluster

# Full Autonomous Curation & Story Export (VLM + Apify + HTML Showcase)
chronocull /path/to/trip_folder --cluster --enrich-apify --curate-ai --export-story

# Rollback anytime
chronocull /path/to/trip_folder --rollback
```
