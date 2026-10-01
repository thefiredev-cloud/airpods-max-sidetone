# Repository Guidelines

## Project Overview

AirPods Sidetone is a small Python utility that gates a PipeWire loopback while a real application captures from AirPods Max.

## Architecture & Data Flow

`sidetone.py` inspects PipeWire source, sink, and capture-client state before enabling the loopback. `sidetone` is the command wrapper. `tests/test_gate.py` exercises the pure gating decision without system calls.

## Key Directories

- `sidetone.py`: graph inspection, gate, and loopback control.
- `sidetone`: command entry point.
- `tests/test_gate.py`: pure gate cases.
- `ruff.toml`: Ruff rule selection.

## Development Commands

```bash
python3 tests/test_gate.py
pytest -v
```

CI uses `pytest -v`; the direct script is the test-runner-free fallback and passed all 8 gate cases in this environment. Ruff is configured for E4, E7, E9, and F rules.

## Code Conventions & Common Patterns

Keep the gating predicate separate from PipeWire side effects. A positive gate requires an active external capture client on the configured headset source; ignore this utility's own loopback and internal/filter nodes.

## Important Files

- `sidetone.py`: source and sink discovery, gate evaluation, and controls.
- `tests/test_gate.py`: boundary cases for the gate.
- `README.md`: user commands and volume bounds.

## Runtime/Tooling Preferences

`sidetone on`, `off`, `level`, and `supervise` change live system audio. Do not run them as incidental tests or alter audio routing without explicit authorization. The project has no network or telemetry path.

## Testing & QA

Run the pure gate tests above for logic changes. They do not establish live PipeWire routing; verify that only with an explicitly authorized audio test slot.
