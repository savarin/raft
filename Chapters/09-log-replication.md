# Chapter 9: Log Replication and Commitment

## Introduction

This chapter covers how the leader replicates log entries to followers and how entries become committed. The leader sends `AppendEntryRequest` messages, tracks each follower's progress, and advances the commit index when a majority has replicated an entry. This is the heart of Raft's consistency guarantee.

## 9.1 The Leader's Responsibility

Once elected, the leader has five ongoing responsibilities:

1. **Send heartbeats**: Periodic empty `AppendEntryRequest` messages to maintain authority
2. **Accept client commands**: Append new entries to its own log
3. **Replicate entries**: Send entries to followers
4. **Advance commit index**: When a majority has replicated an entry
5. **Step down if isolated**: If no followers respond

The leader is the single point of coordination. All changes flow through it.

## 9.2 Tracking Follower Progress

The leader maintains two dictionaries:

```python
self.next_index = {identifier: len(self.log) for identifier in self.config}
self.match_index = {identifier: None for identifier in self.config}
self.match_index[self.identifier] = len(self.log) - 1
```

**`next_index[i]`**: The next log index to send to follower `i`. Initialized optimistically to the end of the leader's log (assuming followers are caught up).

**`match_index[i]`**: The highest log index known to be replicated on follower `i`. Initialized to `None` (nothing confirmed), except for the leader itself.

These are updated as followers respond to `AppendEntryRequest` messages.

## 9.3 Creating AppendEntryRequest

The `create_append_entries_arguments` method builds the request parameters:

```python
def create_append_entries_arguments(
    self, target: int
) -> Tuple[int, int, int, List[raftlog.LogEntry], int]:
    assert self.next_index is not None
    next_index = self.next_index[target]

    assert next_index is not None
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
        self.log[next_index:],
        self.commit_index,
    )
```

For each follower, the request includes:
- `current_term`: Leader's term (for follower to update)
- `previous_index`: Index immediately before new entries
- `previous_term`: Term at that index (for verification)
- `entries`: Log entries starting at `next_index`
- `commit_index`: Leader's commit index (for follower to update)

For heartbeats, `entries` is empty (no new entries to replicate).

## 9.4 Handling AppendEntryRequest (Follower Side)

When a follower receives `AppendEntryRequest`:

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
    # Update term/role if needed
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.LEADER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # If not follower, reject
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.AppendEntryResponse(
                target, source, self.current_term, False, len(entries)
            )
        ]

    # Try to append entries
    success = raftlog.append_entries(
        self.log, previous_index, previous_term, entries
    )

    # Update commit index
    if commit_index > self.commit_index:
        self.commit_index = min(commit_index, len(self.log) - 1)

    return [
        raftmessage.AppendEntryResponse(
            target, source, self.current_term, success, len(entries)
        )
    ]
```

The key steps:

1. **State update**: If the leader's term is higher, update and become follower
2. **Role check**: Only followers process append requests
3. **Log append**: Call `raftlog.append_entries` (from Chapter 3)
4. **Commit update**: Advance local commit index based on leader's
5. **Response**: Report success/failure and how many entries were sent

## 9.5 Handling AppendEntryResponse (Leader Side)

When the leader receives a response:

```python
def handle_append_entries_response(
    self,
    source: int,
    target: int,
    current_term: int,
    success: bool,
    entries_length: int,
) -> List[raftmessage.Message]:
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    if self.role != raftrole.Role.LEADER:
        return []

    if success:
        self.update_indexes(source, entries_length)
        assert self.has_followers is not None
        self.has_followers = True
        return []

    # Failure: retry with earlier entries
    assert self.next_index is not None
    self.next_index[source] = self.next_index[source] - 1

    return [
        raftmessage.AppendEntryRequest(
            target,
            source,
            *self.create_append_entries_arguments(source),
        )
    ]
```

Two paths:

**Success**: Update the tracking indexes and mark that we have active followers.

**Failure**: Decrement `next_index` and retry. The follower's log diverges from the leader's at some point—we need to find where and send entries from there.

## 9.6 Log Reconciliation in Action

When a follower's log diverges, the leader backs up until finding a match. Consider Figure 7 scenario (b) where a follower is missing many entries:

```
Leader:   [1] [1] [1] [4] [4] [5] [5] [6] [6] [6]
Follower: [1] [1] [1] [4]

Initial: leader sends with previous_index=9, previous_term=6
→ Follower rejects (doesn't have index 9)

Retry: previous_index=8, previous_term=6
→ Follower rejects (doesn't have index 8)

... continues until ...

Retry: previous_index=3, previous_term=4
→ Follower accepts! Has entry at index 3 with term 4
→ Appends entries 4-9
```

The test demonstrates this:

```python
def test_handle_message_b(paper_log, logs_by_identifier):
    leader_state, follower_state, _, request = init_raft_states(
        paper_log, logs_by_identifier["b"], None
    )

    for i in range(6):
        response = follower_state.handle_message(request[0])
        assert not response[0].success
        request = leader_state.handle_message(response[0])

    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 6
```

Six rejections, then success with 6 entries.

## 9.7 Advancing the Commit Index

An entry is committed when replicated on a majority. The leader checks this after each successful response:

```python
def update_indexes(self, target: int, entries_length: int) -> None:
    assert self.next_index is not None and self.match_index is not None
    self.next_index[target] += entries_length
    self.match_index[target] = self.next_index[target] - 1

    non_null_match_index_count, potential_commit_index = self.get_index_metrics()

    # Need majority
    if non_null_match_index_count < self.count_majority():
        return None

    # Safety check: only commit entries from current term
    update_commit_index = (
        len(self.log) > 0
        and self.log[potential_commit_index].term == self.current_term
    )

    if update_commit_index or self.experimental_mode:
        self.commit_index = potential_commit_index
```

The `get_index_metrics` function finds the median `match_index`:

```python
def get_index_metrics(self) -> Tuple[int, int]:
    assert self.match_index is not None
    non_null_match_index_values = sorted(
        [value for value in self.match_index.values() if value is not None]
    )

    # Get median value
    median_match_index = self.count_majority() - 1 - self.count_null_match_index()

    if 0 <= median_match_index < len(non_null_match_index_values):
        potential_commit_index = non_null_match_index_values[median_match_index]
    else:
        potential_commit_index = -1

    return non_null_match_index_count, potential_commit_index
```

## 9.8 The Commit Index Safety Rule

The check `self.log[potential_commit_index].term == self.current_term` is crucial. Without it, Raft would violate safety.

Consider the Figure 8 scenario from the paper:

```
Initial state:
  S1 (leader term 2): [1, 2]
  S2: [1, 2]
  S3: [1]
  S4: [1]
  S5: [1]

S1 replicates entry 2 to S2, then crashes.
S5 becomes leader (term 3) with votes from S3, S4.
S5 appends entry 3, replicates to S3, S4.

  S1: [1, 2]
  S2: [1, 2]
  S3: [1, 3]  ← New entry, term 3
  S4: [1, 3]
  S5 (leader): [1, 3]

Now S1 comes back and becomes leader (term 4).
S1 continues replicating entry 2...
```

If S1 could commit entry 2 just because it's on a majority (S1, S2, S3 after reconciliation), that would be wrong—S5 already has committed entry 3 at that position.

The rule "only commit entries from current term" prevents this. S1 must first replicate a new entry (term 4) and commit that, which implicitly commits everything before it.

The tests verify this:

```python
def test_commit_with_requirement() -> None:
    # ... setup Figure 8 scenario ...

    # Without the rule, entry 2 would be committed
    # But with the rule, commit_index doesn't advance
    assert state_2.log[1] == raftlog.LogEntry(2, "2")
    assert state_2.commit_index == 0  # NOT 1

def test_commit_without_requirement() -> None:
    # Same scenario with experimental_mode=True
    # (disables the safety rule)

    assert state_2.log[1] == raftlog.LogEntry(2, "2")
    assert state_2.commit_index == 1  # WRONG! This would be unsafe

    # After S5 takes over, entry 2 gets overwritten
    assert state_2.log[1] == raftlog.LogEntry(3, "3")  # Lost entry 2!
```

## 9.9 Propagating Commit Index

Followers learn the commit index from the leader's `AppendEntryRequest.commit_index`:

```python
if commit_index > self.commit_index:
    self.commit_index = min(commit_index, len(self.log) - 1)
```

The `min` ensures the follower doesn't set a commit index beyond its log length. This can happen if the follower is behind and receives a heartbeat before catching up.

## 9.10 Client Commands

When a client sends a command, the leader appends it locally:

```python
def handle_client_log_append(
    self, source: int, target: int, item: str
) -> List[raftmessage.Message]:
    if self.role != raftrole.Role.LEADER:
        raise Exception("Not able to append entries when not leader.")

    self.log.append(raftlog.LogEntry(self.current_term, item))

    assert self.next_index is not None and self.match_index is not None
    self.next_index[target] = len(self.log)
    self.match_index[target] = len(self.log) - 1

    return []
```

The entry is replicated to followers on the next heartbeat. Once a majority acknowledges, it's committed.

## Conclusion

The leader replicates entries by sending `AppendEntryRequest` messages and tracking progress with `nextIndex` and `matchIndex`. Failed appends trigger retries with earlier log portions until logs match. Entries are committed when replicated on a majority, but only entries from the current term advance the commit index (the Figure 8 safety rule). Followers learn the commit index through heartbeats. This mechanism ensures all nodes eventually have identical committed logs.
