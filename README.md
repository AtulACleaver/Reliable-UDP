# Reliable UDP File Transfer Protocol

An end-to-end reliable file transfer system implemented over UDP in Python, comparing three classic Automatic Repeat reQuest (ARQ) protocols: **Stop-and-Wait (SW)**, **Go-Back-N (GBN)**, and **Selective Repeat (SR)** across an emulated impairment channel with dynamic Retransmission Timeout (RTO) estimation.

Every transfer is strictly verified against **SHA-256** cryptographic hashes to guarantee 100% byte-for-byte data integrity.

*Course:* CS30003 Computer Networks, CA1 (Project P3).

---

## 👥 The Team

| Name | Role & Responsible Files | GitHub |
| :--- | :--- | :--- |
| **Atul Anand** | `packet.py` (header, checksum, framing), `stopwait.py` (SW ARQ), `transfer.py` (CLI runner), `README.md` | [@AtulACleaver](https://github.com/AtulACleaver) |
| **Shashank Shekhar Pandey** | `gbn.py` (Go-Back-N pipelining, cumulative ACKs, single-timer window) | [@ssp0009](https://github.com/ssp0009) |
| **Aqifa Aziz** | `sr.py` (Selective Repeat ARQ, `TimerHeap` per-packet timers, out-of-order buffer) | [@Aqifa10](https://github.com/Aqifa10) |
| **Archit Kumar** | `channel.py` (impairment proxy, Blake2b hashing), `rto.py` (FixedRTO & RFC 6298 AdaptiveRTO) | [@Archit1302-wolf](https://github.com/Archit1302-wolf) |
| **Harsha Darshita Ojha** | `experiments.py` (46-config sweep matrix, resume engine), `plots.py` (visualization & claim report) | [@HarshaDarshitaOjha](https://github.com/HarshaDarshitaOjha) |

---

## 🚀 Quick Start & How to Run

Requires **Python 3.11** or newer. No third-party packages are required for protocol execution. Generating matplotlib plots requires dependencies in `requirements.txt`.

```bash
# Optional: install matplotlib for plots
pip install -r requirements.txt
```

### 1. Run a Single Transfer (`transfer.py`)
Run an isolated transfer on localhost through the channel proxy and receive live performance metrics in JSON format:

```bash
# Selective Repeat with window=32 over 5% packet loss
python transfer.py --protocol sr --window 32 --loss 0.05

# Go-Back-N with window=16 over 2% packet loss and 1% packet reordering
python transfer.py --protocol gbn --window 16 --loss 0.02 --reorder 0.01

# Stop-and-Wait baseline with 1% packet loss
python transfer.py --protocol sw --loss 0.01
```

**Available Options:**
* `--protocol {sw, gbn, sr}`: ARQ protocol to execute (default: `gbn`).
* `--window <int>`: Sender window capacity in packets (default: `32`; forced to `1` for `sw`).
* `--loss <float>`: Channel loss probability between `0.0` and `1.0` (default: `0.0`).
* `--reorder <float>`: Channel reordering probability (default: `0.0`).
* `--delay <float>`: One-way channel propagation delay in seconds (default: `0.002` = 2 ms).
* `--rto {adaptive, adaptive-nokarn, fixed:<sec>}`: RTO estimation policy (default: `adaptive`).
* `--size <int>`: File payload size in bytes (default: `65536` = 64 KB).
* `--seed <int>`: Master random seed for deterministic impairments (default: `1`).

### 2. Run the Full Test Suite (`test_all.py`)
Run all 66 unit and integration tests across packet framing, channel impairments, RTO estimators, and all three protocols:

```bash
# Run every single test
python test_all.py

# Run only tests matching a keyword (e.g. sr, gbn, sw, channel, rto, experiments, plots)
python test_all.py sr
python test_all.py gbn
python test_all.py experiments
```

### 3. Run the Experiment Matrix (`experiments.py`)
Executes the comprehensive 46-configuration parameter matrix (sweeping loss, window sizes, reordering, and RTO policies):

```bash
# Quick validation run: 46 configs x 1 seed on 64 KB (writes quick.csv and quick_traces.csv)
python experiments.py --quick

# Full experimental evaluation: 46 configs x 3 seeds on 1 MB (writes results.csv and traces.csv)
python experiments.py
```
*Note: If an experiment run is interrupted, re-running the command automatically resumes without re-executing already verified configurations.*

### 4. Generate Visualization Plots & Claim Report (`plots.py`)
Parses experiment data, averages across seeds, and outputs the five comparison figures and `claim.md`:

```bash
# Generate plots from the quick matrix run
python plots.py quick

# Generate plots from the full results.csv run
python plots.py
```
Outputs are written to the `plots/` directory:
* `plots/plot1_goodput_vs_loss.png`: Goodput vs. Loss Rate across SW, GBN, and SR.
* `plots/plot2_goodput_vs_window.png`: Goodput vs. Window Size ($W \in \{1, 4, 16, 32, 64, 128\}$) at 5% loss.
* `plots/plot3_reorder_impact.png`: Goodput and Retransmissions vs. Reorder Probability ($W=32$).
* `plots/plot4_rto_comparison.png`: Fixed (0.5s) vs. RFC 6298 Adaptive vs. Adaptive without Karn's rule.
* `plots/plot5_rto_trace.png`: Measured RTT samples vs. SRTT vs. dynamic RTO envelope over time.
* `plots/claim.md`: Automated analysis verifying the pipelining advantage and SR efficiency.

---

## 🏗️ Architecture & Component Design

```
+------------------+         +-------------------------------+         +--------------------+
|      Sender      |  DATA   |         Channel Proxy         |  DATA   |      Receiver      |
|  (send_file)     | ------> |  channel.py damage()          | ------> |  (recv_file)       |
|                  |         |  - Loss, Corruption, Dup      |         |                    |
|                  |  ACK    |  - Delay, Jitter, Reorder     |  ACK    |                    |
|                  | <------ |  - Token Bucket Rate Limiter  | <------ |                    |
+------------------+         +-------------------------------+         +--------------------+
```

### 1. Wire Packet Specification (`packet.py`)
All protocols share a uniform 13-byte binary header packed with network byte order (`!IIBHH`):
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Sequence Number                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Acknowledgment Number                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|     Flags     |            Length             |   Checksum    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Payload Data ...                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
* **Sequence / Ack Number** (`uint32`): Identifies packet index and cumulative/individual ACK target.
* **Flags** (`uint8`): Bitmask flags: `DATA = 0x01`, `ACK = 0x02`, `FIN = 0x04`.
* **Length** (`uint16`): Payload byte count (up to 1024 bytes per packet).
* **Checksum** (`uint16`): RFC 1071 one's complement Internet checksum computed over header and payload.

### 2. Impairment Channel (`channel.py`)
Emulates realistic network degradation on UDP traffic in userspace:
* **Deterministic Decisions:** Uses `hashlib.blake2b` keyed on `(seed, salt, seq, attempt)` so all protocols encounter identical loss patterns for the same seed, eliminating stream-position artifacts.
* **Impairments:** Stochastic packet loss, bit flips (corruption), packet duplication, propagation delay with jitter, and controlled out-of-order reordering.
* **Rate Limiter:** Token bucket algorithm emulating bounded link bandwidth.

### 3. RTO Estimators (`rto.py`)
* **`FixedRTO`**: Static timeout interval (e.g. 500 ms) doubling upon timeout (exponential backoff).
* **`AdaptiveRTO` (RFC 6298 Jacobson/Karels)**:
  $$\text{SRTT} \leftarrow (1 - \alpha) \cdot \text{SRTT} + \alpha \cdot R \quad (\alpha = 0.125)$$
  $$\text{RTTVAR} \leftarrow (1 - \beta) \cdot \text{RTTVAR} + \beta \cdot |\text{SRTT} - R| \quad (\beta = 0.25)$$
  $$\text{RTO} \leftarrow \text{SRTT} + 4 \cdot \text{RTTVAR}$$
* **Karn's Algorithm (1987)**: Samples from retransmitted packets are ignored to eliminate ambiguity about which transmission triggered the ACK.

---

## 🔄 Protocol Comparison

| Feature | Stop-and-Wait (`sw.py`) | Go-Back-N (`gbn.py`) | Selective Repeat (`sr.py`) |
| :--- | :--- | :--- | :--- |
| **Window Size** | $W = 1$ | $W \ge 1$ (e.g. 32) | $W \ge 1$ (e.g. 32) |
| **Timers** | 1 timer (per packet) | 1 timer (oldest unacknowledged) | Multiple timers via `TimerHeap` (per packet) |
| **ACK Semantics** | Individual ACK | Cumulative ACK (slides base to `ack + 1`) | Individual ACK for each arrived packet |
| **Receiver Buffering** | None (discards out-of-order) | None (discards out-of-order, re-ACKs base) | Out-of-order buffer (delivers contiguous runs) |
| **Loss Recovery** | Retransmit single packet after RTO | Retransmit entire unacked window $[base .. nextseq-1]$ | Retransmit **only** the packet that timed out |
| **Goodput under Loss** | Low (serialization delay) | Medium (redundant retransmissions) | **Highest** (optimal channel utilization) |

---

## 🧪 Shared Function Interface

All three protocols adhere strictly to the shared API contract:

```python
def send_file(sock: socket.socket, peer: tuple[str, int], data: bytes, window: int, rto: Any) -> dict:
    """Returns {"packets", "sent", "retx", "timeouts", "dup_acks", "seconds"}"""

def recv_file(sock: socket.socket, window: int) -> bytes:
    """Returns received payload bytes after verifying stream termination."""
```
