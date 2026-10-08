"""channel.py: the middleman that damages traffic on purpose. Owner: Archit.

The sender and receiver never talk directly. Every packet goes through the
channel, which decides what happens to it: dropped, corrupted, duplicated,
delayed, or held back so later packets overtake it.

Each direction has its own random generator built from the seed, so the
same seed makes the same decisions for the same packets.
"""

