# CS-30003 Coding Assignment 1: Reliable Data Transfer over UDP

## Team 
| Name | Roll Number | Section |
|---|---|---|
| Aqifa Aziz | 2405334 | CSE-34 |
| Atul Anand | 2405339 | CSE-34 |
| Harsha Darshita Ojha | 2405352 | CSE-34 |
| Shashank Shekhar Pandey | 2405382 | CSE-34 |
| Archit Kumar | 24052551 | CSE-34 |

## Lane Ownership
- **Lane 1 (Atul):** `rdt/packet.py`, `rdt/transport.py`, `rdt/stop_and_wait.py`
- **Lane 2 (Shashank):** `rdt/go_back_n.py`
- **Lane 3 (Aqifa):** `rdt/selective_repeat.py`
- **Lane 4 (Archit):** `rdt/rto.py`, `rdt/channel.py`
- **Lane 5 (Harsha):** `experiments/run_matrix.py`, `experiments/plots.py`

## Running the Application
**Sender:**
```bash
python -m app.sender --file <file_path> --host <host> --port <port> --protocol <protocol> --window <window_size> --seed <seed>
```

**Receiver:**
```bash
python -m app.receiver --output <output_path> --port <port> --protocol <protocol>
```

## Running Experiments
Run the experiment matrix:
```bash
python -m experiments.run_matrix
```
Regenerate plots:
```bash
python -m experiments.plots
```

## Running Tests
Run the test suite using pytest:
```bash
pytest tests/
```

## Repository Conventions
- One branch per lane (e.g., `lane-1`, `lane-2`, etc.).
- Review is required before merging into `main`.
- Every member commits under their own name and email.
