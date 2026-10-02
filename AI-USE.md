# AI Assistance Log

### Entry 1: 2026-10-02 (Shashank - Lane 2 Day 1 Setup)
- **Files touched:**
  - `docs/plan/week-1.md`
  - `docs/plan/week-1-shashank.md`
  - `rdt/__init__.py`
  - `rdt/window.py`
  - `tests/__init__.py`
  - `tests/test_gbn_window.py`
  - `Makefile`
  - `tasks.py`
- **What was asked:**
  - Set up Shashank's Week 1 (Day 1) environment for the Go-Back-N (GBN) lane in Reliable-UDP.
- **What was accepted:**
  - Week 1 plan documentation export into `docs/plan/week-1-shashank.md`.
  - Pure-logic `SendWindow` class scaffold with invariants, docstrings, and method stubs.
  - TDD unit test suite in `tests/test_gbn_window.py` specifying all 7 window behaviors (can_send, on_ack, outstanding, is_empty, full window bounds, stale acks).
  - Setup of `Makefile` and `tasks.py` runner for `check` and `smoke`.
- **What the human rewrites / must write by hand:**
  - Core arithmetic logic inside `rdt/window.py` (`can_send`, `next_seq`, `on_ack`, `outstanding`, `is_empty`) is stubbed with `NotImplementedError` and must be written by hand by Shashank for individual viva grading.
