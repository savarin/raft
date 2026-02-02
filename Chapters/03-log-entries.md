# Chapter 3: Log Entries and the Append Operation

## Introduction

This chapter covers the replicated log at Raft's core. The log is an ordered sequence of commands that all nodes must eventually agree on. The `append_entries` operation, implemented in `raftlog.py`, enforces the invariants that make this agreement safe. Understanding the log is essential—every other part of Raft exists to maintain log consistency.

## 3.1 The LogEntry Data Structure

Each entry in the log carries two pieces of information:

```python
@dataclasses.dataclass
class LogEntry:
    term: int
    item: str

    def __equals__(self, other) -> bool:
        return self.term == other.term and self.item == other.item

    def __repr__(self) -> str:
        return f"LogEntry({str(self.term)}, '{self.item}')"
```

The `term` field records which term the entry was created in. This matters because entries from different terms might conflict. The `item` field holds the actual command (in this implementation, just a string; a real system would have structured commands).

Why include the term? Consider a scenario where two different leaders in different terms both try to add an entry at the same index. Without term information, you couldn't tell which entry should win. With terms, the rule is simple: higher term wins.

## 3.2 The Log Continuity Condition

A Raft log must never have gaps. If a log has entries at indices 0, 1, and 2, the next entry must go at index 3. You can't skip to index 5.

The `append_entries` operation enforces this through two parameters:

- `previous_index`: The index of the entry immediately before the new entries
- `previous_term`: The term of that entry

For an append to succeed, the log must contain an entry at `previous_index` with term equal to `previous_term`. This creates a chain of verification back to the beginning of the log.

```
Index:     0       1       2       3       4
         ┌───┐   ┌───┐   ┌───┐   ┌───┐   ┌───┐
Term:    │ 1 │ → │ 1 │ → │ 2 │ → │ 2 │ → │ 3 │
         └───┘   └───┘   └───┘   └───┘   └───┘

To append at index 5:
  previous_index = 4
  previous_term = 3  (must match log[4].term)
```

If the check fails, the append returns `False` and the caller knows to try with an earlier `previous_index`.

## 3.3 Implementing append_entries

Here's the complete implementation from `raftlog.py`:

```python
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
    # replaced, remove that entry and following entries.
    for n, entry in enumerate(entries, start=previous_index + 1):
        if n < len(log) and log[n].term != entry.term:
            del log[n:]
            break

    for i, entry in enumerate(entries):
        if not is_equal_entry(log, previous_index + i, entry):
            return False

    log += entries[len(log) - previous_index - 1 :]

    return True
```

Let's walk through each step:

**Step 1: Gap check**
```python
if previous_index >= len(log):
    return False
```
If `previous_index` is beyond the current log, we can't append without creating a gap.

**Step 2: Term verification**
```python
if previous_index >= 0 and log[previous_index].term != previous_term:
    return False
```
The entry at `previous_index` must have the expected term. This catches inconsistencies early.

**Step 3: Conflict resolution**
```python
for n, entry in enumerate(entries, start=previous_index + 1):
    if n < len(log) and log[n].term != entry.term:
        del log[n:]
        break
```
If an existing entry has a different term than the new entry at the same index, delete it and everything after. The leader's log wins.

**Step 4: Append new entries**
```python
log += entries[len(log) - previous_index - 1 :]
```
Add entries that aren't already present. The slice handles the case where some entries are duplicates.

## 3.4 Conflict Resolution

Why is it safe to delete follower entries that conflict with the leader? Because of two properties:

1. **Leader completeness**: A leader's log contains all committed entries. If an entry was committed, a majority acknowledged it, and the election rules ensure any new leader has it.

2. **Log matching**: If two logs have an entry with the same index and term, all preceding entries are identical.

So when a follower has entries the leader doesn't, those entries were never committed. They might be from a leader that crashed before replicating to a majority. Deleting them is safe—they were never "official."

```
Leader log:    [1:a] [1:b] [2:c]
Follower log:  [1:a] [1:b] [1:x] [1:y]
                              ↑
                      Conflict at index 2:
                      leader has term 2, follower has term 1

After append_entries:
Follower log:  [1:a] [1:b] [2:c]
               (entries [1:x] and [1:y] deleted)
```

## 3.5 The Figure 7 Scenarios

The Raft paper's Figure 7 shows various log states that can occur after a series of failures. The test suite exercises these exact scenarios:

```python
@pytest.fixture
def paper_log():
    paper_log = [
        raftlog.LogEntry(1, "1"),
        raftlog.LogEntry(1, "1"),
        raftlog.LogEntry(1, "1"),
    ]
    paper_log += [raftlog.LogEntry(4, "4"), raftlog.LogEntry(4, "4")]
    paper_log += [raftlog.LogEntry(5, "5"), raftlog.LogEntry(5, "5")]
    paper_log += [
        raftlog.LogEntry(6, "6"),
        raftlog.LogEntry(6, "6"),
        raftlog.LogEntry(6, "6"),
    ]
    return paper_log
```

This represents the leader's log in Figure 7. The test then creates follower logs matching scenarios (a) through (f):

```python
def test_append_entries_paper(logs_by_identifier):
    # Figure 7a - follower missing one entry
    assert not raftlog.append_entries(
        logs_by_identifier["a"], 9, 6, [raftlog.LogEntry(6, "6")]
    )

    # Figure 7b - follower missing many entries
    assert not raftlog.append_entries(
        logs_by_identifier["b"], 9, 6, [raftlog.LogEntry(6, "6")]
    )
```

These tests verify that `append_entries` correctly rejects appends that would create inconsistencies, and correctly reconciles divergent logs.

## 3.6 Idempotency and Duplicate Handling

Network failures mean messages might be delivered multiple times. The `append_entries` operation handles this gracefully through the `is_equal_entry` check:

```python
def is_equal_entry(log: List[LogEntry], previous_index: int, entry: LogEntry) -> bool:
    if previous_index < len(log) - 1 and log[previous_index + 1] != entry:
        return False
    return True
```

If you try to append entries that are already present (same index, same content), the operation succeeds without duplicating them. The slice in the final append handles this:

```python
log += entries[len(log) - previous_index - 1 :]
```

This only appends entries beyond the current log length, skipping duplicates.

## Conclusion

The replicated log stores an ordered sequence of commands. The `append_entries` operation enforces two key invariants: logs never have gaps (checked via `previous_index`), and entries at the same index must have matching terms (checked via `previous_term`). When conflicts occur, the leader's entries overwrite the follower's—this is safe because uncommitted entries are expendable. These invariants, verified through Figure 7 test cases, ensure all nodes eventually converge to identical logs.
