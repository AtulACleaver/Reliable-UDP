# Reliable UDP

Three ways to send a file reliably over UDP: Stop-and-Wait, Go-Back-N and
Selective Repeat. A channel in the middle drops, corrupts, duplicates,
delays and reorders packets on purpose. Every transfer checks the received
file's SHA-256.

CS30003 Computer Networks, CA1, project P3.

## Team

| Name | Files | GitHub |
| --- | --- | --- |
| Atul Anand | packet.py, stopwait.py, transfer.py | AtulACleaver |
| Shashank Shekhar Pandey | gbn.py | ssp0009 |
| Aqifa Aziz | sr.py | |
| Archit Kumar | channel.py, rto.py | |
| Harsha Darshita Ojha | experiments.py, plots.py | |

## Run it

Python 3.11 or newer. Nothing to install for the protocols; the plots need
`pip install -r requirements.txt`.

```
python transfer.py --protocol sr --window 32 --loss 0.05     # one transfer, prints one JSON line
python test_all.py                                         # every test
python test_all.py gbn                                     # only tests with "gbn" in the name
python experiments.py --quick                              # quick check of the whole matrix
python experiments.py                                      # the real run -> results.csv, traces.csv
python plots.py                                            # results.csv -> plots/*.png, plots/claim.md
```

On Windows use `py` instead of `python`.

## How the pieces fit

```
 sender (send_file)        channel.py                  receiver (recv_file)
       |  DATA  -------->  damage(): loss, corrupt,  ---------> |
       |                   dup, delay+jitter, reorder           |
       |  <--------  ACK   (same, decided separately)  <------- |
```

`transfer.py` starts all three on this machine, runs the protocol you pick
and compares hashes.

## The interface (do not change without telling the group)

Every protocol file has the same two functions:

```python
send_file(sock, peer, data, window, rto) -> dict
    # returns {"packets", "sent", "retx", "timeouts", "dup_acks", "seconds"}
recv_file(sock, window) -> bytes
```

Packet: 13-byte header `!IIBHH` = seq, ack, flags, length, checksum.
Flags: DATA 1, ACK 2, FIN 4. Payload up to 1024 bytes.

RTO objects (`rto.py`): `value()`, `sample(rtt, resent)`, `backoff()`, `forward()`.
