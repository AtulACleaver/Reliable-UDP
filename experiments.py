"""experiments.py: runs every experiment and writes results.csv. Owner: Harsha.

    python experiments.py --quick     one seed, 64 KB, writes quick.csv: checks everything runs
    python experiments.py             the real run: 46 configs x 3 seeds on 1 MB

If it stops halfway, run the same command again: rows already in the CSV
with sha256_ok True are skipped.
"""

import csv
import hashlib
import os
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Tuple

import channel
from channel import Channel
import rto
from rto import make_rto
import stopwait
import gbn

try:
    import sr
except ImportError:
    sr = None


def configs() -> list[dict]:
    """Return the 46 experiment settings, without running a transfer."""
    out = []
    for protocol in ("sw", "gbn", "sr"):
        for loss in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2):
            out.append({
                "sweep": "loss", "protocol": protocol,
                "window": 1 if protocol == "sw" else 32,
                "rto": "adaptive", "loss": loss, "reorder": 0.0,
            })
    for protocol in ("gbn", "sr"):
        for window in (1, 4, 16, 32, 64, 128):
            out.append({
                "sweep": "window", "protocol": protocol, "window": window,
                "rto": "adaptive", "loss": 0.05, "reorder": 0.0,
            })
    for protocol in ("gbn", "sr"):
        for reorder in (0.0, 0.01, 0.05, 0.1, 0.2):
            out.append({
                "sweep": "reorder", "protocol": protocol, "window": 32,
                "rto": "adaptive", "loss": 0.0, "reorder": reorder,
            })
    for protocol in ("gbn", "sr"):
        for rto in ("fixed:0.5", "adaptive", "adaptive-nokarn"):
            out.append({
                "sweep": "rto", "protocol": protocol, "window": 32,
                "rto": rto, "loss": 0.05, "reorder": 0.0,
            })
    return out


def run_transfer(
    protocol: str,
    window: int,
    rto_spec: str,
    loss: float = 0.0,
    reorder: float = 0.0,
    seed: int = 1,
    file_size: int = 65536,
    delay: float = 0.002,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute a single end-to-end file transfer through an emulated channel.

    Wires sender -> Channel proxy -> receiver on loopback, validates SHA-256 integrity,
    and returns transfer statistics dictionary along with any RTO trace records.
    """
    if protocol == "sw":
        proto = stopwait
    elif protocol == "gbn":
        proto = gbn
    elif protocol == "sr":
        if sr is None or not hasattr(sr, "send_file") or not hasattr(sr, "recv_file"):
            raise NotImplementedError("Selective Repeat protocol (sr.py) not yet implemented")
        proto = sr
    else:
        raise ValueError(f"Unknown protocol {protocol!r}: must be 'sw', 'gbn', or 'sr'")

    orig_linger = getattr(proto, "LINGER", 2.0)
    proto.LINGER = 0.1  # Fast teardown on loopback measurements

    # Deterministic payload based on file size and seed
    data = bytes((i * 31 + seed * 17) % 256 for i in range(file_size))

    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind(("127.0.0.1", 0))
    r_addr = recv_sock.getsockname()

    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    proxy_sock.bind(("127.0.0.1", 0))
    p_addr = proxy_sock.getsockname()

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send_sock.bind(("127.0.0.1", 0))

    ch = Channel(loss=loss, corrupt=0.0, dup=0.0, delay=delay, jitter=0.0, reorder=reorder, seed=seed)
    stop_proxy = threading.Event()
    received_chunks = []

    def proxy():
        client_addr = None
        proxy_sock.settimeout(0.3)
        while not stop_proxy.is_set():
            try:
                raw, addr = proxy_sock.recvfrom(65535)
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break

            if addr == r_addr:
                if client_addr:
                    for pkt in ch.damage(raw, "to_sender"):
                        try:
                            proxy_sock.sendto(pkt, client_addr)
                        except OSError:
                            pass
            else:
                client_addr = addr
                for pkt in ch.damage(raw, "to_receiver"):
                    try:
                        proxy_sock.sendto(pkt, r_addr)
                    except OSError:
                        pass

    pt = threading.Thread(target=proxy, daemon=True)
    pt.start()

    rt = threading.Thread(
        target=lambda: received_chunks.append(proto.recv_file(recv_sock, window)),
        daemon=True,
    )
    rt.start()

    rto_obj = make_rto(rto_spec)
    trace_records = []

    try:
        raw_stats = proto.send_file(send_sock, p_addr, data, window, rto_obj)
        rt.join(timeout=5.0)
        stop_proxy.set()
        pt.join(timeout=1.0)

        received_bytes = received_chunks[0] if received_chunks else b""
        sha256_ok = (
            hashlib.sha256(received_bytes).digest() == hashlib.sha256(data).digest()
        )

        elapsed = float(raw_stats.get("seconds", 0.0))
        goodput_bps = (8.0 * file_size / elapsed) if elapsed > 0 else 0.0
        goodput_kbps = (file_size / elapsed / 1024.0) if elapsed > 0 else 0.0

        stats = {
            "packets": int(raw_stats.get("packets", 0)),
            "sent": int(raw_stats.get("sent", 0)),
            "retx": int(raw_stats.get("retx", 0)),
            "timeouts": int(raw_stats.get("timeouts", 0)),
            "dup_acks": int(raw_stats.get("dup_acks", 0)),
            "seconds": round(elapsed, 4),
            "goodput_bps": round(goodput_bps, 2),
            "goodput_kbps": round(goodput_kbps, 2),
            "sha256_ok": sha256_ok,
        }

        if hasattr(rto_obj, "trace") and isinstance(rto_obj.trace, list):
            for idx, entry in enumerate(rto_obj.trace):
                trace_records.append({
                    "protocol": protocol,
                    "rto": rto_spec,
                    "seed": seed,
                    "sample_idx": idx,
                    "rtt": entry.get("rtt", 0.0),
                    "srtt": entry.get("srtt", 0.0),
                    "rttvar": entry.get("rttvar", 0.0),
                    "rto_value": entry.get("rto", 0.0),
                    "resent": entry.get("resent", False),
                })

        return stats, trace_records

    finally:
        stop_proxy.set()
        proxy_sock.close()
        recv_sock.close()
        send_sock.close()
        proto.LINGER = orig_linger


RESULT_FIELDS = [
    "sweep", "protocol", "window", "rto", "loss", "reorder",
    "seed", "file_size", "packets", "sent", "retx", "timeouts",
    "dup_acks", "seconds", "goodput_bps", "goodput_kbps", "sha256_ok"
]

TRACE_FIELDS = [
    "sweep", "protocol", "rto", "seed", "sample_idx",
    "rtt", "srtt", "rttvar", "rto_value", "resent"
]


def load_completed_keys(csv_path: str) -> set:
    """Read CSV and return set of parameter tuples already verified with sha256_ok True."""
    completed = set()
    if not os.path.exists(csv_path):
        return completed

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if str(r.get("sha256_ok", "")).lower() in ("true", "1"):
                    key = (
                        r.get("sweep", ""),
                        r.get("protocol", ""),
                        int(r.get("window", 0)),
                        r.get("rto", ""),
                        float(r.get("loss", 0.0)),
                        float(r.get("reorder", 0.0)),
                        int(r.get("seed", 0)),
                        int(r.get("file_size", 0)),
                    )
                    completed.add(key)
    except Exception:
        pass
    return completed


def append_result(csv_path: str, row: Dict[str, Any]) -> None:
    """Append a single experiment result row to CSV with durable flush."""
    d = os.path.dirname(csv_path)
    if d:
        os.makedirs(d, exist_ok=True)
    write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in RESULT_FIELDS})
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def append_traces(traces_path: str, traces: List[Dict[str, Any]]) -> None:
    """Append RTO trace records to trace CSV with durable flush."""
    if not traces:
        return
    d = os.path.dirname(traces_path)
    if d:
        os.makedirs(d, exist_ok=True)
    write_header = not os.path.exists(traces_path) or os.path.getsize(traces_path) == 0
    with open(traces_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACE_FIELDS)
        if write_header:
            writer.writeheader()
        for t in traces:
            writer.writerow({k: t.get(k, "") for k in TRACE_FIELDS})
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def run_experiments(
    quick: bool = False,
    custom_configs: List[Dict[str, Any]] = None,
    results_file: str = None,
    traces_file: str = None,
) -> int:
    """Run experiment matrix with resume support and write results to CSV.

    Args:
        quick: If True, executes one seed on 64 KB writing quick.csv/quick_traces.csv.
               If False, executes 3 seeds on 1 MB writing results.csv/traces.csv.
        custom_configs: Optional subset of configuration dictionaries to run.
        results_file: Custom output path for results CSV.
        traces_file: Custom output path for traces CSV.

    Returns:
        int: Number of failed transfers.
    """
    if quick:
        seeds = [1]
        file_size = 64 * 1024
        res_path = results_file or "quick.csv"
        tr_path = traces_file or "quick_traces.csv"
    else:
        seeds = [1, 2, 3]
        file_size = 1024 * 1024
        res_path = results_file or "results.csv"
        tr_path = traces_file or "traces.csv"

    all_configs = custom_configs if custom_configs is not None else configs()
    completed = load_completed_keys(res_path)
    total_runs = len(all_configs) * len(seeds)
    run_idx = 0
    failures = 0

    print(f"Running experiments ({'--quick' if quick else 'full matrix'}): {len(all_configs)} configs, {len(seeds)} seeds, file_size={file_size}")
    print(f"Output: {res_path}, Traces: {tr_path}")
    print(f"Resuming: {len(completed)} verified runs already present in {res_path}\n")

    for cfg in all_configs:
        sweep = cfg["sweep"]
        proto = cfg["protocol"]
        win = cfg["window"]
        rto_policy = cfg["rto"]
        loss = cfg["loss"]
        reorder = cfg["reorder"]

        for seed in seeds:
            run_idx += 1
            key = (sweep, proto, win, rto_policy, loss, reorder, seed, file_size)

            if key in completed:
                print(f"[{run_idx}/{total_runs}] SKIP (already verified) {sweep}:{proto} w={win} loss={loss} reorder={reorder} rto={rto_policy} seed={seed}")
                continue

            print(f"[{run_idx}/{total_runs}] RUN {sweep}:{proto} w={win} loss={loss} reorder={reorder} rto={rto_policy} seed={seed} ...", end=" ", flush=True)

            try:
                stats, traces = run_transfer(
                    protocol=proto,
                    window=win,
                    rto_spec=rto_policy,
                    loss=loss,
                    reorder=reorder,
                    seed=seed,
                    file_size=file_size,
                )

                row = {
                    "sweep": sweep,
                    "protocol": proto,
                    "window": win,
                    "rto": rto_policy,
                    "loss": loss,
                    "reorder": reorder,
                    "seed": seed,
                    "file_size": file_size,
                    **stats,
                }

                append_result(res_path, row)

                for t in traces:
                    t["sweep"] = sweep
                append_traces(tr_path, traces)

                if row.get("sha256_ok"):
                    print(f"PASS (goodput={row.get('goodput_kbps')} KB/s, retx={row.get('retx')}, {row.get('seconds')}s)")
                else:
                    failures += 1
                    print("FAIL (hash mismatch)")

            except NotImplementedError as exc:
                print(f"SKIP ({exc})")
            except Exception as exc:
                failures += 1
                print(f"ERROR: {type(exc).__name__}: {exc}")
                err_row = {
                    "sweep": sweep,
                    "protocol": proto,
                    "window": win,
                    "rto": rto_policy,
                    "loss": loss,
                    "reorder": reorder,
                    "seed": seed,
                    "file_size": file_size,
                    "packets": 0,
                    "sent": 0,
                    "retx": 0,
                    "timeouts": 0,
                    "dup_acks": 0,
                    "seconds": 0.0,
                    "goodput_bps": 0.0,
                    "goodput_kbps": 0.0,
                    "sha256_ok": False,
                }
                append_result(res_path, err_row)

    print(f"\nCompleted: {run_idx}/{total_runs} runs checked. Failures: {failures}")
    return failures


def main() -> None:
    quick = any(arg.lower() in ("--quick", "quick", "-q") for arg in sys.argv[1:])
    ret = run_experiments(quick=quick)
    sys.exit(1 if ret > 0 else 0)


if __name__ == "__main__":
    main()



