"""
The core of the Raft algorithm involves appending new entries to the log. The
append_entries operation is subject to a number of constraints.

- Duplicate transactions have no adverse effect.
- The log may never have gaps.
- When adding to the log, information about prior entry must match. This is
  also known as the log-continuity condition.
- If entries have a term number less than the term of the entry to be replaced,
  the entries with the smaller term and successive ones are deleted.


AppendEntries RPCs section in Figure 2 of Raft paper:

Receiver implementation:
 2. Reply false if log doesn’t contain an entry at prevLogIndex whose term
    matches prevLogTerm (§5.3)
 3. If an existing entry conflicts with a new one (same index but different
    terms), delete the existing entry and all that follow it (§5.3)
 4. Append any new entries not already in the log
"""

from typing import List
import dataclasses


@dataclasses.dataclass
class LogEntry:
    term: int
    item: str

    def __equals__(self, other) -> bool:
        return self.term == other.term and self.item == other.item

    def __repr__(self) -> str:
        return f"LogEntry({str(self.term)}, '{self.item}')"


def is_equal_entry(log: List[LogEntry], previous_index: int, entry: LogEntry) -> bool:
    if previous_index < len(log) - 1 and log[previous_index + 1] != entry:
        return False

    return True


def append_entries(
    log: List[LogEntry],
    previous_index: int,
    previous_term: int,
    entries: List[LogEntry],
) -> bool:
    # Check index rewrite does not create gaps. If it does, return False.
    if previous_index >= len(log):
        return False

    # Check term number of previous entry matches previous_term.
    if previous_index >= 0 and log[previous_index].term != previous_term:
        return False

    # If term number of existing entry is less than term of entry to be
    # replaced, remove that entry and following entries. Conflict resolved by
    # using the later term as truth since there can only be one leader.
    for n, entry in enumerate(entries, start=previous_index + 1):
        if n < len(log) and log[n].term != entry.term:
            del log[n:]
            break

    for i, entry in enumerate(entries):
        if not is_equal_entry(log, previous_index + i, entry):
            return False

    log += entries[len(log) - previous_index - 1 :]

    return True
