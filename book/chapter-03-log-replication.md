# Chapter 3: Log Replication

*In which we discover how leaders distribute commands to followers, why logs can diverge in surprising ways, and the subtle rule that prevents committed entries from vanishing.*

---

## The Purpose of the Log

Elections establish who leads. But leadership is only valuable if the leader can *do something*—specifically, accept commands from clients and ensure those commands are durably replicated across the cluster.

The replicated log is Raft's mechanism for this. Every command that enters the system becomes a log entry. The leader appends the entry to its own log, then replicates it to followers. Once a majority of servers have the entry, it's considered **committed**—safe from any failure that doesn't destroy more than half the cluster.

```
                        Client
                          │
                          │ "set x = 42"
                          ▼
    ┌─────────────────────────────────────────────────────────┐
    │                      LEADER                             │
    │                                                         │
    │   log: [..., (term=5, "set x = 42")]                   │
    │                        │                                │
    └────────────────────────│────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
         ┌─────────┐   ┌─────────┐   ┌─────────┐
         │Follower │   │Follower │   │Follower │
         │   A     │   │   B     │   │   C     │
         └─────────┘   └─────────┘   └─────────┘

         After majority (leader + 2 followers) have the entry:
         → Entry is COMMITTED
         → Safe to apply to state machine
         → Safe to respond to client
```

This chapter explores the mechanics of this replication: how entries flow from leader to followers, how the system handles followers with divergent logs, and when entries become safe to commit.

---

## The AppendEntries RPC

All log replication flows through a single RPC: **AppendEntries**. This message serves dual purposes:

1. **Heartbeat**: When sent with no entries, it maintains leader authority and prevents election timeouts
2. **Replication**: When sent with entries, it distributes new commands to followers

The message structure:

```python
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int           # Leader's term
    previous_index: int         # Index of entry immediately before new ones
    previous_term: int          # Term of that entry
    entries: List[LogEntry]     # New entries (empty for heartbeat)
    commit_index: int           # Leader's commit index
```

The `previous_index` and `previous_term` fields are the key to Raft's consistency guarantees. Before accepting new entries, a follower verifies that its log matches the leader's at the specified position. This is the **consistency check**.

---

## The Log Matching Property

Raft maintains a powerful invariant called the **Log Matching Property**:

> If two logs contain an entry with the same index and term, then:
> 1. The entries are identical (same command)
> 2. The logs are identical in all preceding entries

This property emerges from two rules:

1. **Leaders create at most one entry per index per term** — A leader appends entries sequentially, never overwriting
2. **Followers only accept entries that pass the consistency check** — The `previous_index`/`previous_term` fields must match

The implementation enforces this in `raftlog.py`:

```python
def append_entries(
    log: List[LogEntry],
    previous_index: int,
    previous_term: int,
    entries: List[LogEntry],
) -> bool:
    # Check index rewrite does not create gaps
    if previous_index >= len(log):
        return False

    # Check term number of previous entry matches previous_term
    if previous_index >= 0 and log[previous_index].term != previous_term:
        return False

    # ... handle conflicts and append ...
    return True
```

The first check prevents gaps: you can't add entry 10 if you don't have entry 9. The second check is the consistency check proper: the entry at `previous_index` must have term `previous_term`.

Together, these checks create an inductive guarantee. If entry *n* matches, and we've verified that entry *n-1* matches (via the consistency check), then by induction, all entries 0 through *n* match.

---

## nextIndex and matchIndex: Tracking Followers

A leader must track two pieces of information for each follower:

| Field | Purpose | Initialization |
|-------|---------|----------------|
| `nextIndex[i]` | Next entry to send to follower *i* | `len(log)` (optimistic) |
| `matchIndex[i]` | Highest entry known to be replicated on follower *i* | `None` (unknown) |

The implementation:

```python
case raftrole.Operation.INITIALIZE:
    self.next_index = {
        identifier: len(self.log) for identifier in self.config
    }

case raftrole.Operation.INITIALIZE:
    self.match_index = {identifier: None for identifier in self.config}
    self.match_index[self.identifier] = len(self.log) - 1
```

When a new leader takes office, it assumes all followers are caught up (`nextIndex` = log length). This is optimistic—followers might be behind—but the protocol will correct this assumption through backtracking.

The `matchIndex` starts as `None` because the leader doesn't know what followers have. Only after a successful AppendEntries response does the leader know for certain.

---

## Creating an AppendEntries Request

When the leader needs to send entries to a follower, it constructs the request based on `nextIndex`:

```python
def create_append_entries_arguments(
    self, target: int
) -> Tuple[int, int, int, List[raftlog.LogEntry], int]:
    next_index = self.next_index[target]
    previous_index = next_index - 1
    previous_term = (
        self.log[previous_index].term
        if len(self.log) > 0 and previous_index >= 0
        else -1
    )

    return (
        self.current_term,
        previous_index,
        previous_term,
        self.log[next_index:],  # All entries from next_index onward
        self.commit_index,
    )
```

Let's trace through an example:

```
Leader's log (length 10):
    Index:  0    1    2    3    4    5    6    7    8    9
    Term:   1    1    1    4    4    5    5    6    6    6
    Entry:  a    b    c    d    e    f    g    h    i    j

next_index[follower_2] = 10  (follower is caught up)

create_append_entries_arguments(follower_2):
    previous_index = 10 - 1 = 9
    previous_term = log[9].term = 6
    entries = log[10:] = []  (empty, this is a heartbeat)
```

For a follower that's behind:

```
next_index[follower_3] = 7  (follower is missing entries 7, 8, 9)

create_append_entries_arguments(follower_3):
    previous_index = 7 - 1 = 6
    previous_term = log[6].term = 5
    entries = log[7:] = [(6, h), (6, i), (6, j)]
```

The request tells the follower: "After your entry at index 6 (which should have term 5), append these three entries."

---

## Handling AppendEntries: The Follower's Perspective

When a follower receives an AppendEntries request, it processes it in `handle_append_entries_request`:

```python
def handle_append_entries_request(
    self,
    source: int,
    target: int,
    current_term: int,
    previous_index: int,
    previous_term: int,
    entries: List[raftlog.LogEntry],
    commit_index: int,
) -> List[raftmessage.Message]:
    # First: update state based on leader's term
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.LEADER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # If not follower (e.g., we're a leader or candidate), reject
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.AppendEntryResponse(
                target, source, self.current_term, False, len(entries)
            )
        ]

    # Attempt the append
    success = raftlog.append_entries(
        self.log, previous_index, previous_term, entries
    )

    # Update commit index based on leader's commit index
    if commit_index > self.commit_index:
        self.commit_index = min(commit_index, len(self.log) - 1)

    return [
        raftmessage.AppendEntryResponse(
            target, source, self.current_term, success, len(entries)
        )
    ]
```

The follower:

1. Updates its term if the leader's term is higher
2. Rejects if it's not a follower (stale message)
3. Attempts the append via `raftlog.append_entries`
4. Updates its commit index if the leader has committed further
5. Returns success or failure

---

## The Backtracking Algorithm

What happens when a follower's log doesn't match?

Consider a follower with a shorter log:

```
Leader's log:
    Index:  0    1    2    3    4    5    6    7    8    9
    Term:   1    1    1    4    4    5    5    6    6    6

Follower's log:
    Index:  0    1    2    3    4    5    6    7    8
    Term:   1    1    1    4    4    5    5    6    6

Leader sends: previous_index=9, previous_term=6, entries=[]
Follower: "I don't have index 9!" → reject (success=False)
```

The leader handles rejection in `handle_append_entries_response`:

```python
def handle_append_entries_response(
    self,
    source: int,
    target: int,
    current_term: int,
    success: bool,
    entries_length: int,
) -> List[raftmessage.Message]:
    # ... state change handling ...

    if self.role != raftrole.Role.LEADER:
        return []

    if success:
        self.update_indexes(source, entries_length)
        self.has_followers = True
        return []

    # If not successful, decrement next_index and retry
    self.next_index[source] = self.next_index[source] - 1

    return [
        raftmessage.AppendEntryRequest(
            target,
            source,
            *self.create_append_entries_arguments(source),
        )
    ]
```

On failure, the leader decrements `next_index` and immediately retries:

```
Round 1:
    Leader: next_index[2] = 10
    Leader sends: previous_index=9, entries=[]
    Follower rejects (doesn't have index 9)

Round 2:
    Leader: next_index[2] = 9
    Leader sends: previous_index=8, entries=[(6, j)]
    Follower accepts! (has index 8 with term 6)
    Follower appends entry j

Round 3:
    Leader receives success
    Leader: next_index[2] = 10, match_index[2] = 9
```

This backtracking continues until the leader finds a position where the logs match. From there, all subsequent entries are sent and accepted.

---

## Figure 7: A Taxonomy of Divergent Logs

The Raft paper's Figure 7 illustrates how logs can diverge after various failure scenarios. The implementation includes test cases for all of them.

### The Leader's Log (Reference)

```
Index:  0    1    2    3    4    5    6    7    8    9
Term:   1    1    1    4    4    5    5    6    6    6
```

This is `paper_log` in the test suite:

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

### Scenario (a): Missing One Entry

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower a: 1  1  1  4  4  5  5  6  6
            0  1  2  3  4  5  6  7  8
```

The follower is simply one entry behind. One round of backtracking:

```python
def test_handle_message_a(...):
    # Initial heartbeat fails (follower missing index 9)
    response = follower_state.handle_message(request[0])
    assert not response[0].success

    # Leader decrements next_index and retries with entry at index 9
    request = leader_state.handle_message(response[0])
    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 1

    # Leader updates indexes
    leader_state.handle_message(response[0])
    assert leader_state.next_index[2] == 10
```

### Scenario (b): Missing Many Entries

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower b: 1  1  1  4
            0  1  2  3
```

The follower missed entries from terms 4, 5, and 6. Six rounds of backtracking:

```python
def test_handle_message_b(...):
    for i in range(6):
        response = follower_state.handle_message(request[0])
        assert not response[0].success
        assert leader_state.next_index[2] == 10 - i
        request = leader_state.handle_message(response[0])

    # Finally succeeds, sending 6 entries at once
    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 6
```

The backtracking finds the match point at index 3, then sends all six missing entries in one batch.

### Scenario (c): Longer Log, Same Terms

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower c: 1  1  1  4  4  5  5  6  6  6  6
            0  1  2  3  4  5  6  7  8  9  10
```

The follower has *more* entries than the leader—but they don't conflict. The consistency check passes immediately:

```python
def test_handle_message_c(...):
    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 0  # Heartbeat, no new entries
```

### Scenario (d): Longer Log with Higher Terms

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower d: 1  1  1  4  4  5  5  6  6  6  7  7
            0  1  2  3  4  5  6  7  8  9  10 11
```

The follower was briefly a leader in term 7 and appended entries. But it lost the election (perhaps to our current leader in term 6, through a complex failure scenario). The consistency check still passes because entries 0-9 match:

```python
def test_handle_message_d(...):
    response = follower_state.handle_message(request[0])
    assert response[0].success
```

The follower's extra entries (from its brief term-7 leadership) remain in its log but will never be committed. Future appends from the current leader will overwrite them.

### Scenario (e): Conflicting Entries

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower e: 1  1  1  4  4  4  4
            0  1  2  3  4  5  6
```

The follower has entries at indices 5 and 6, but with term 4 instead of term 5. This is a genuine conflict—the follower received entries from a different term-4 leader that our current leader never saw.

Five rounds of backtracking until reaching index 4:

```python
def test_handle_message_e(...):
    for i in range(5):
        response = follower_state.handle_message(request[0])
        assert not response[0].success
        request = leader_state.handle_message(response[0])

    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 5
```

### Scenario (f): Deeply Divergent Log

```
Leader:     1  1  1  4  4  5  5  6  6  6
Follower f: 1  1  1  2  2  2  3  3  3  3  3
            0  1  2  3  4  5  6  7  8  9  10
```

The follower was partitioned during terms 4, 5, and 6. It saw different leaders in terms 2 and 3. Its log is completely different from index 3 onward.

Seven rounds of backtracking:

```python
def test_handle_message_f(...):
    for i in range(7):
        response = follower_state.handle_message(request[0])
        assert not response[0].success
        request = leader_state.handle_message(response[0])

    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 7
```

---

## Conflict Resolution

When the backtracking process finds conflicting entries, they must be removed. The `append_entries` function handles this:

```python
def append_entries(
    log: List[LogEntry],
    previous_index: int,
    previous_term: int,
    entries: List[LogEntry],
) -> bool:
    # ... consistency checks ...

    # If an existing entry conflicts with a new one (same index,
    # different terms), delete the existing entry and all that follow
    for n, entry in enumerate(entries, start=previous_index + 1):
        if n < len(log) and log[n].term != entry.term:
            del log[n:]
            break

    # Append new entries
    log += entries[len(log) - previous_index - 1:]
    return True
```

The deletion rule is crucial: if entry *n* conflicts, we delete entries *n* and all following entries. This is safe because:

1. Conflicting entries came from a different leader
2. That leader's entries were never committed (or our current leader couldn't have been elected)
3. The current leader's entries take precedence

---

## Visualizing the Full Reconciliation

Let's trace through Scenario (f) in detail:

```
Initial state:
    Leader:     [1, 1, 1, 4, 4, 5, 5, 6, 6, 6]
    Follower f: [1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3]

Round 1: Leader sends prev_idx=9, prev_term=6, entries=[]
    Follower: log[9].term = 3 ≠ 6 → REJECT

Round 2: Leader sends prev_idx=8, prev_term=6, entries=[6]
    Follower: log[8].term = 3 ≠ 6 → REJECT

Round 3: Leader sends prev_idx=7, prev_term=6, entries=[6, 6]
    Follower: log[7].term = 3 ≠ 6 → REJECT

Round 4: Leader sends prev_idx=6, prev_term=5, entries=[6, 6, 6]
    Follower: log[6].term = 3 ≠ 5 → REJECT

Round 5: Leader sends prev_idx=5, prev_term=5, entries=[5, 6, 6, 6]
    Follower: log[5].term = 2 ≠ 5 → REJECT

Round 6: Leader sends prev_idx=4, prev_term=4, entries=[5, 5, 6, 6, 6]
    Follower: log[4].term = 2 ≠ 4 → REJECT

Round 7: Leader sends prev_idx=3, prev_term=4, entries=[4, 5, 5, 6, 6, 6]
    Follower: log[3].term = 2 ≠ 4 → REJECT

Round 8: Leader sends prev_idx=2, prev_term=1, entries=[4, 4, 5, 5, 6, 6, 6]
    Follower: log[2].term = 1 = 1 → ACCEPT!

    Before append: [1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3]
    Conflict at index 3: log[3].term=2 ≠ entry.term=4
    Delete log[3:]: [1, 1, 1]
    Append entries: [1, 1, 1, 4, 4, 5, 5, 6, 6, 6]

Final state:
    Leader:     [1, 1, 1, 4, 4, 5, 5, 6, 6, 6]
    Follower f: [1, 1, 1, 4, 4, 5, 5, 6, 6, 6]  ← Now identical!
```

The follower's eight conflicting entries (terms 2 and 3) have been replaced with the leader's seven entries (terms 4, 5, and 6). The logs are now identical.

---

## Commit Index Advancement

Having entries replicated isn't enough—we need to know when they're *committed*. A leader advances `commit_index` when an entry has been replicated to a majority.

The implementation calculates this in `update_indexes`:

```python
def update_indexes(self, target: int, entries_length: int) -> None:
    self.next_index[target] += entries_length
    self.match_index[target] = self.next_index[target] - 1

    non_null_match_index_count, potential_commit_index = self.get_index_metrics()

    # Require at least majority of match_index to be non-null
    if non_null_match_index_count < self.count_majority():
        return None

    # Require entry to be from leader's current term
    update_commit_index = (
        len(self.log) > 0
        and self.log[potential_commit_index].term == self.current_term
    )

    if update_commit_index or self.experimental_mode:
        self.commit_index = potential_commit_index
```

The `get_index_metrics` function finds the highest index replicated on a majority:

```python
def get_index_metrics(self) -> Tuple[int, int]:
    non_null_match_index_values = sorted(
        [value for value in self.match_index.values() if value is not None]
    )
    non_null_match_index_count = len(non_null_match_index_values)

    # Find the median (the value that a majority has reached)
    median_match_index = self.count_majority() - 1 - self.count_null_match_index()

    if 0 <= median_match_index < len(non_null_match_index_values):
        potential_commit_index = non_null_match_index_values[median_match_index]
    else:
        potential_commit_index = -1

    return non_null_match_index_count, potential_commit_index
```

In a 3-node cluster, once 2 nodes have an entry (leader + 1 follower), that entry can potentially be committed.

---

## The Current-Term Requirement

Notice this check in `update_indexes`:

```python
update_commit_index = (
    len(self.log) > 0
    and self.log[potential_commit_index].term == self.current_term
)
```

A leader can only directly commit entries from its **current term**. This seems restrictive—why not commit older entries that have achieved majority replication?

The answer involves a subtle safety issue illustrated by the Raft paper's Figure 8. Consider this scenario:

```
Time 1: S1 is leader (term 2), replicates entry to S2
        S1: [1, 2]
        S2: [1, 2]
        S3: [1]
        S4: [1]
        S5: [1]

Time 2: S1 crashes. S5 becomes leader (term 3), appends entry
        S1: [1, 2]  (crashed)
        S2: [1, 2]
        S3: [1, 3]
        S4: [1, 3]
        S5: [1, 3]

Time 3: S5 crashes. S1 recovers, becomes leader (term 4)
        S1 replicates term-2 entry to S3:
        S1: [1, 2]
        S2: [1, 2]
        S3: [1, 2]  ← Now on majority!
        S4: [1, 3]
        S5: [1, 3]  (crashed)

        If S1 commits the term-2 entry here...

Time 4: S1 crashes again. S5 recovers, becomes leader (term 5)
        S5 has higher-term entry (term 3), so it can win
        S5 replicates term-3 entry to everyone:
        S1: [1, 3]  ← Term-2 entry OVERWRITTEN!
        S2: [1, 3]
        S3: [1, 3]
        S4: [1, 3]
        S5: [1, 3]

        The "committed" term-2 entry has vanished!
```

This violates safety—committed entries must never disappear. The solution: **only commit entries from the current term**. Older entries become committed indirectly when a current-term entry after them is committed.

The test suite validates both behaviors:

```python
def test_commit_with_requirement() -> None:
    # With the current-term requirement, the term-2 entry
    # is NOT committed, so when S5 overwrites it, no
    # safety violation occurs
    # ...
    assert prior_log[prior_commit_index] == state_2.log[prior_commit_index]

def test_commit_without_requirement() -> None:
    # experimental_mode=True disables the requirement
    # This demonstrates the safety violation
    # ...
    assert prior_log[prior_commit_index] != state_2.log[prior_commit_index]
```

The `experimental_mode` flag exists specifically to demonstrate this failure mode.

---

## Follower Commit Index Updates

Followers learn about commits through the `commit_index` field in AppendEntries:

```python
# In handle_append_entries_request:
if commit_index > self.commit_index:
    self.commit_index = min(commit_index, len(self.log) - 1)
```

The `min` is important: a follower might receive a commit index for entries it doesn't have yet. It can only mark entries as committed if it actually has them.

---

## The Consensus Test

The test suite includes a comprehensive consensus test that simulates a 3-node cluster with two divergent followers:

```python
def test_consensus(...):
    # Leader has paper_log (10 entries)
    # Follower A has log_a (9 entries, missing last one)
    # Follower B has log_b (4 entries, way behind)

    leader_state, follower_a_state, follower_b_state, request = init_raft_states(
        paper_log, logs_by_identifier["a"], logs_by_identifier["b"]
    )

    assert leader_state.next_index == {1: 10, 2: 10, 3: 10}
    assert leader_state.match_index == {1: 9, 2: None, 3: None}
    assert leader_state.commit_index == -1
```

After reconciling Follower A:

```python
    # Follower A needs one round
    response_a = follower_a_state.handle_message(request[0])
    request_a = leader_state.handle_message(response_a[0])
    response_a = follower_a_state.handle_message(request_a[0])
    leader_state.handle_message(response_a[0])

    assert leader_state.next_index == {1: 10, 2: 10, 3: 10}
    assert leader_state.match_index == {1: 9, 2: 9, 3: None}
    assert leader_state.commit_index == 9  # Now committed! Majority achieved
```

The leader can now commit because a majority (itself + Follower A) has the entries.

After reconciling Follower B:

```python
    # Follower B needs six rounds of backtracking
    response_b = follower_b_state.handle_message(request[1])
    for i in range(6):
        request_b = leader_state.handle_message(response_b[0])
        response_b = follower_b_state.handle_message(request_b[0])

    leader_state.handle_message(response_b[0])
    assert leader_state.match_index == {1: 9, 2: 9, 3: 9}  # All caught up
```

Finally, followers learn about the commit:

```python
    request = leader_state.handle_leader_heartbeat(followers=[2, 3])
    follower_a_state.handle_message(request[0])
    follower_b_state.handle_message(request[1])

    assert follower_a_state.commit_index == 9
    assert follower_b_state.commit_index == 9
```

The heartbeat carries the leader's `commit_index`, allowing followers to update their own.

---

## Client Requests

When a client wants to append an entry, the leader handles it in `handle_client_log_append`:

```python
def handle_client_log_append(
    self, source: int, target: int, item: str
) -> List[raftmessage.Message]:
    """
    Client adds a log entry (received by leader).
    """
    if self.role != raftrole.Role.LEADER:
        raise Exception("Not able to append entries when not leader.")

    self.log.append(raftlog.LogEntry(self.current_term, item))

    # Update own indexes
    self.next_index[target] = len(self.log)
    self.match_index[target] = len(self.log) - 1

    return []
```

The entry is appended locally and the leader's own `match_index` is updated. The entry will be replicated to followers on the next heartbeat cycle.

---

## The Replication Pipeline

Putting it all together, here's the complete flow of a command through the system:

```
┌──────────────────────────────────────────────────────────────────┐
│                     COMMAND REPLICATION FLOW                     │
└──────────────────────────────────────────────────────────────────┘

1. Client sends command to leader
   │
   ▼
2. Leader appends entry to local log
   log.append(LogEntry(current_term, command))
   │
   ▼
3. Leader sends AppendEntries to all followers (next heartbeat)
   For each follower:
       entries = log[next_index[follower]:]
       │
       ▼
4. Follower receives AppendEntries
   ├── Consistency check passes?
   │   ├── Yes: Append entries, return success
   │   └── No:  Return failure
   │
   ▼
5. Leader receives response
   ├── Success?
   │   ├── Yes: Update next_index, match_index
   │   │        Check if majority → advance commit_index
   │   └── No:  Decrement next_index, retry immediately
   │
   ▼
6. Once committed, entry is safe
   Leader includes commit_index in future AppendEntries
   Followers update their commit_index
   Entry can be applied to state machine
```

---

## What We've Learned

This chapter explored the mechanics of log replication in Raft:

- **AppendEntries** serves as both heartbeat and replication mechanism
- **The consistency check** ensures logs can only diverge at uncommitted entries
- **nextIndex and matchIndex** track what each follower has
- **Backtracking** finds the point where logs match, then replicates from there
- **Figure 7 scenarios** show the variety of ways logs can diverge
- **Conflict resolution** removes conflicting entries and replaces them with the leader's
- **Commit index** advances when a majority has an entry
- **The current-term requirement** prevents a subtle safety violation

The key insight is that log replication is **eventually consistent**: given time, all servers will have identical logs. The consistency check ensures that this convergence never corrupts committed entries—only uncommitted entries from failed leaders can be overwritten.

---

## Looking Ahead

Chapter 4 takes us from algorithm to implementation: the network layer, message serialization, timeouts, and testing strategies. We'll also examine what this implementation intentionally omits—snapshots, membership changes, persistence—and understand the design trade-offs involved.

---

## Exercises

1. **Backtracking Optimization**: The implementation decrements `nextIndex` by one on each failure. The Raft paper mentions an optimization where the follower returns enough information to skip multiple indices at once. How would you implement this? What information would the follower need to return?

2. **Duplicate Entries**: The docstring in `raftlog.py` says "Duplicate transactions have no adverse effect." Trace through `append_entries` to understand why appending the same entry twice is safe.

3. **Commit Index Race**: Consider this sequence:
   - Leader sends AppendEntries with commit_index=5
   - Follower has log length 3, so it sets commit_index=2 (min of 5 and 2)
   - Later AppendEntries brings follower up to length 7
   - What is the follower's commit_index now? Is this correct?

4. **The Empty Log Edge Case**: When the leader's log is empty, what are `previous_index` and `previous_term` in AppendEntries? Trace through `create_append_entries_arguments` to find out.

5. **Hands-On**: Start a 3-node cluster. Use the client to append entries `a b c` to the leader. Kill one follower. Append more entries `d e f`. Restart the follower. Use the `self` command to observe the logs before and after the follower catches up.

6. **Safety Violation**: Read the `test_commit_without_requirement` test carefully. Draw the sequence of events that leads to a committed entry being overwritten. Why does the current-term requirement prevent this?

---

*The final chapter explores the practical aspects of building a Raft implementation: networking, serialization, and the design decisions that make theory into running code.*
