# Graph Report - airpods-max-sidetone  (2026-10-21)

## Corpus Check
- 7 files · ~3,949 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .toml 1, .service 1)

## Summary
- 80 nodes · 148 edges · 8 communities (6 shown, 2 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- sidetone.py
- test_gate.py
- start_loopback
- airpods-max-sidetone
- Repository Guidelines
- supervise
- install.sh
- uninstall.sh

## God Nodes (most connected - your core abstractions)
1. `supervise()` - 17 edges
2. `start_loopback()` - 12 edges
3. `run()` - 11 edges
4. `node_id()` - 10 edges
5. `gather_status()` - 9 edges
6. `Repository Guidelines` - 9 edges
7. `airpods-max-sidetone` - 9 edges
8. `read_volume()` - 8 edges
9. `set_volume()` - 6 edges
10. `stop_loopback()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Runtime/Tooling Preferences` --references--> `supervise()`  [INFERRED]
  AGENTS.md → sidetone.py
- `Usage` --references--> `supervise()`  [INFERRED]
  README.md → sidetone.py
- `run_case()` --calls--> `evaluate_gate()`  [INFERRED]
  tests/test_gate.py → sidetone.py

## Import Cycles
- None detected.

## Communities (8 total, 2 thin omitted)

### Community 0 - "sidetone.py"
Cohesion: 0.28
Nodes (10): cmd_level(), cmd_on(), cmd_status(), cmd_supervise(), ensure_state_dir(), fmt_state(), main(), read_level() (+2 more)

### Community 1 - "test_gate.py"
Cohesion: 0.15
Nodes (3): main(), run_case(), test_gate()

### Community 2 - "start_loopback"
Cohesion: 0.32
Nodes (11): _cleanup_stale_nodes(), cmd_off(), gather_status(), node_id(), pw_dump(), read_volume(), run(), set_volume() (+3 more)

### Community 3 - "airpods-max-sidetone"
Cohesion: 0.17
Nodes (11): airpods-max-sidetone, Configuration, Development, How it is supervised, License, Project layout, Quick start, Requirements (+3 more)

### Community 4 - "Repository Guidelines"
Cohesion: 0.20
Nodes (9): Architecture & Data Flow, Code Conventions & Common Patterns, Development Commands, Important Files, Key Directories, Project Overview, Repository Guidelines, Runtime/Tooling Preferences (+1 more)

### Community 5 - "supervise"
Cohesion: 0.20
Nodes (5): evaluate_gate(), jcmd(), log(), snapshot(), supervise()

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `supervise()` connect `supervise` to `sidetone.py`, `start_loopback`, `airpods-max-sidetone`, `Repository Guidelines`?**
  _High betweenness centrality (0.456) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `supervise()` (e.g. with `Runtime/Tooling Preferences` and `Usage`) actually correct?**
  _`supervise()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Why does `Usage` connect `airpods-max-sidetone` to `supervise`?**
  _High betweenness centrality (0.228) - this node is a cross-community bridge._