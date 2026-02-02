# Chapter 2: The Log

The replicated log is Raft's core data structure. Every client command becomes a log entry. Consensus means agreeing on the log's contents—which entries exist, in what order.

This chapter examines the log's structure, the invariants that keep it consistent, and the `append_entries` function that enforces those invariants. Understanding the log is prerequisite to understanding everything else: log replication (Chapter 6) is about synchronizing logs across servers; elections (Chapter 7) use log state to decide who can become leader.

## Log Entries

A log is a sequence of entries. Each entry has two fields:

```python
@dataclasses.dataclass
class LogEntry:
    term: int
    item: str
```

The `item` is the command—what the client wants to execute. In this implementation, it's just a string; a real system would have structured commands like "set key=value" or "transfer $100 from A to B."

The `term` identifies when the entry was created. Terms are Raft's logical clock: they increase monotonically, and each term has at most one leader. When a leader creates an entry, it stamps it with the current term.

Why do entries need terms? Because terms identify conflicts. If two entries have the same index but different terms, they came from different leaders—and only one can be correct. The later term wins.

## The Log as a List

In this implementation, logs are Python lists:

```python
self.log: List[raftlog.LogEntry] = []
```

The Raft paper uses 1-indexing (the first entry is at index 1), but Python lists are 0-indexed. This implementation uses 0-indexing throughout. The conversion is straightforward—just subtract 1 from paper indices—but it does mean that "previous_index = -1" represents "before the first entry."

When the log is empty and we want to append the first entry, we say: the previous index is -1 (nothing before it), and the previous term is -1 (a sentinel value meaning "no term"). This handles the base case cleanly.

## The Log Continuity Invariant

The fundamental constraint on logs is that they can never have gaps. You can't have entries at indices 0, 1, and 3 with nothing at index 2.

This is the "log continuity" property. Every append must reference the immediately preceding entry by its index and term. If the preceding entry doesn't exist or doesn't match, the append fails.

Why does this matter? Because it gives us a powerful guarantee: **if two logs agree at index N, they agree on all entries from 0 to N.** The logs might diverge after N, but everything before N is identical.

This property cascades. When we append entry N+1, we verify that entry N matches. When we appended entry N, we verified that entry N-1 matched. The chain of verification goes back to the beginning.

The consequence is that committed entries are safe. Once a majority of servers have an entry at index N with term T, any future leader must have that entry—because any future leader must have a log that agrees with a majority, and any majority overlaps with the committed majority.

## Conflict Resolution

What happens when entries conflict—same index, different terms?

```
Leader's log:  [1, 1, 1, 4, 4]
Follower's log: [1, 1, 1, 2, 2, 3]
```

The first three entries match (all term 1). But at index 3, the leader has term 4 and the follower has term 2. These entries are incompatible.

The rule is simple: **the later term wins.** Term 4 is later than term 2, so the leader's entry replaces the follower's. And we don't just replace index 3—we delete index 3 and everything after it. The follower's log becomes `[1, 1, 1, 4, 4]`, matching the leader's.

Why is this safe? Because there's only one leader per term. If the follower had an entry from term 2, it came from the term-2 leader. If the current leader is in term 4 or later, the term-2 leader is long gone. The term-4 leader's entries are authoritative.

The code that handles this is in `append_entries`:

```python
# If term number of existing entry is less than term of entry to be
# replaced, remove that entry and following entries. Conflict resolved by
# using the later term as truth since there can only be one leader.
for n, entry in enumerate(entries, start=previous_index + 1):
    if n < len(log) and log[n].term != entry.term:
        del log[n:]
        break
```

## The `append_entries` Function

Let's walk through `raftlog.append_entries` line by line. This function is the heart of log management:

```python
def append_entries(
    log: List[LogEntry],
    previous_index: int,
    previous_term: int,
    entries: List[LogEntry],
) -> bool:
```

The function takes the current log (which it may modify), the index and term of the entry that should precede the new entries, and the entries to append. It returns True on success, False on failure.

**Step 1: Check for gaps**

```python
if previous_index >= len(log):
    return False
```

If `previous_index` is 5 but the log only has 3 entries (indices 0, 1, 2), there's no entry at index 5. We can't append after it because that would create a gap.

**Step 2: Check term match**

```python
if previous_index >= 0 and log[previous_index].term != previous_term:
    return False
```

If the entry at `previous_index` has a different term than claimed, the logs have diverged. We can't append here—the leader needs to back up and find where the logs actually agree.

The `previous_index >= 0` check handles the empty-log case. When appending to an empty log, `previous_index` is -1, and we skip this check (there's no previous entry to verify).

**Step 3: Resolve conflicts**

```python
for n, entry in enumerate(entries, start=previous_index + 1):
    if n < len(log) and log[n].term != entry.term:
        del log[n:]
        break
```

For each entry we're about to append, check if there's an existing entry at that index with a different term. If so, delete that entry and everything after it. The later term (the one we're appending) takes precedence.

**Step 4: Validate existing entries**

```python
for i, entry in enumerate(entries):
    if not is_equal_entry(log, previous_index + i, entry):
        return False
```

This validates that any entries already in the log at these positions match what we're appending. The `is_equal_entry` helper returns True if the position is beyond the log's current length (fine—we'll append there) or if the existing entry matches. If there's a mismatch that wasn't caught by the conflict resolution in Step 3, something is wrong.

**Step 5: Append new entries**

```python
log += entries[len(log) - previous_index - 1 :]
```

Finally, append entries that aren't already in the log. The slice `entries[len(log) - previous_index - 1 :]` skips entries that already exist (from previous appends) and adds only the new ones.

The function returns True if it succeeds.

## Idempotency

Notice what happens if we send the same `append_entries` twice:

1. First call: entries are appended, function returns True
2. Second call: entries already exist, slice produces nothing new, function returns True

Duplicate appends have no adverse effect. The same entries sent twice result in the same log. This is crucial in a distributed system where messages can be duplicated or retried.

The leader doesn't need to track whether it already sent entries to a follower. It can resend freely. The follower's log ends up correct either way.

## Testing with Figure 7

The Raft paper's Figure 7 shows various ways follower logs can diverge from the leader's. The tests in `test_raftlog.py` reproduce these scenarios:

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

This creates the leader's log from Figure 7: terms 1,1,1,4,4,5,5,6,6,6.

Then the fixture creates variants representing different follower states:
- **Log a**: Missing the last entry (9 entries instead of 10)
- **Log b**: Missing the last 6 entries (only 4 entries)
- **Log c**: Has an extra entry (11 entries)
- **Log d**: Has extra entries with term 7
- **Log e**: Diverged at index 5 with different terms
- **Log f**: Completely different history after index 3

The tests verify that `append_entries` correctly handles each case—rejecting invalid appends, accepting valid ones, and resolving conflicts as needed.

## Conclusion

The log's simplicity is deceptive. It's just a list of entries with term numbers. But the invariants it maintains—no gaps, term-based conflict resolution, idempotency—are what make Raft work.

The `append_entries` function encodes the paper's Figure 2 rules in about 30 lines of Python. Those 30 lines ensure that any committed entry persists across leader failures, that divergent logs converge, and that the system makes progress despite message duplication.

With the log understood, you're ready to see how servers communicate about it. The next chapter catalogs the messages that flow between servers.
