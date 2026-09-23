---
name: rdt-lane-work
description: Guides implementation work on the CS30003 reliable-data-transfer project. Use when adding or changing code in rdt/, channel/, experiments/ or tests/, or when planning a lane task from the weekly plan.
---

# Lane work on the RDT project

## Before writing anything

1. Read contracts/packet.md, contracts/transport.py and contracts/stats.md.
   Every interface you need is there. If it is not, that is a blocker, not a
   design decision you get to make.
2. Identify which lane the task belongs to and confirm the target files are
   owned by that lane in CODEOWNERS.
3. Produce a plan artifact: files touched, functions added, tests added, and
   which contract each one depends on. Stop for approval.

## While implementing

- One concern per commit. A window-slide fix and a logging change are two
  commits.
- Write the failing test first when the behaviour is testable without sockets.
- Pure logic modules (window.py, timers.py, rto.py) must be importable and
  testable with no socket and no real clock. Inject the clock as a parameter
  defaulting to time.monotonic.
- Log with a single structured line per event so the emulator log and the
  transport log can be diffed across runs.

## Before opening the PR

Run exactly what CI runs: `make check` (ruff, then pytest), then
`python tasks.py smoke`. Both green or the PR is not ready.

Fill the PR template honestly. "Contracts touched" should say none.
Append the AI-USE.md entry in the same PR, not later.
