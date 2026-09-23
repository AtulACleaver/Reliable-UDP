---
name: rdt-viva-drill
description: Generates viva-style questions about a specific file or module in the CS30003 RDT project. Use when preparing for the individual viva or when reviewing another teammate's lane to understand it deeply.
---

# Viva drill

Given a file or module, generate questions a viva examiner would ask. Focus on:

1. **Why, not what.** "What does this line do?" is a warm-up. "Why did you
   choose this over the alternative?" is the real question.

2. **Edge cases.** What happens at sequence-number wrap? What if the window is
   full and an ACK arrives for the oldest packet? What if the file is zero
   bytes?

3. **Invariants.** What must always be true about base and nextseqnum? What
   happens if the invariant breaks?

4. **Modifications.** "Change the window size from 4 to 8 — what else has to
   change?" "Add a duplicate-ACK counter — where does it go and what does it
   affect?"

5. **Failure modes.** "The checksum passes but the data is wrong — how?" "The
   timer fires but the packet was already ACKed — what happens?"

Generate 8–12 questions per file, ordered from concept to implementation to
modification. Mark which ones require a code change to answer.
