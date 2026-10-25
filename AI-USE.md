# AI use

Course rule: no AI writes core logic. Core functions are written by their owner.
The stubs hold only signatures and the shared interface.

Core: packet.py (top half), stopwait.py, gbn.py, sr.py, channel.py (damage),
rto.py (the two classes).

## Atul
- Used AI for building `test_all.py` test suite code to review and verify whether my code was working properly.

## Shashank
- Used AI for structuring the pure-logic `SendWindow` harness in `rdt/window.py` and synthesizing the Kurose 3.4.3 FSM diagrams and proofs in `docs/fsm-gbn.md`.
- Used AI for building the Go-Back-N test harnesses in `tests/test_gbn_window.py` and `test_all.py` to verify full window limits, cumulative ACKs, out-of-order packet rejections, and loss recovery.

## Aqifa

## Archit

## Harsha
