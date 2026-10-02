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
  - Core arithmetic logic inside `rdt/window.py` was stubbed with `NotImplementedError` for human implementation.

### Entry 2: 2026-10-03 (Shashank - Lane 2 Week 1 Completion)
- **Files touched:**
  - `rdt/window.py`
  - `docs/fsm-gbn.md`
  - `AI-USE.md`
- **What was asked:**
  - Implement the arithmetic logic for `SendWindow` (`can_send`, `next_seq`, `on_ack`, `outstanding`, `is_empty`) and generate the GBN Sender FSM diagram and narrative to complete Week 1.
- **What was accepted:**
  - Implementation of `can_send` checking `nextseq - base < window`.
  - Implementation of `next_seq` checking window bounds, advancing `nextseq`, and returning the allocated sequence number.
  - Implementation of `on_ack` applying cumulative ACK semantics, ignoring stale/out-of-bounds ACKs, sliding `base = ack + 1`, and returning the slide delta.
  - Implementation of `outstanding` returning `list(range(base, nextseq))` for timeout retransmission.
  - Implementation of `is_empty` checking `base == nextseq`.
  - Generation of Kurose 3.4.3 compliant Mermaid FSM diagram and transition explanations in `docs/fsm-gbn.md`.
  - All 7 unit tests in `tests/test_gbn_window.py` passing green; `ruff check .` passing with 0 errors.
- **What the human rewrote / must review for viva:**
  - The arithmetic logic in `rdt/window.py` and the transitions in `docs/fsm-gbn.md` must be reviewed and practiced by Shashank so he can explain and modify them live during the individual viva.

