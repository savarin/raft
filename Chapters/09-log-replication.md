# Chapter 9: Log Replication and Commitment

## Introduction

This chapter covers how the leader replicates log entries to followers and how entries become committed. The leader sends `AppendEntryRequest` messages, tracks each follower's progress, and advances the commit index when a majority has replicated an entry. This is the heart of Raft's consistency guarantee.

## Sections

### 9.1 The Leader's Responsibility

Once elected, the leader:
1. Sends periodic heartbeats (empty `AppendEntryRequest`)
2. Appends client commands to its log
3. Replicates new entries to followers
4. Advances commit index when safe
5. Steps down if isolated from followers

### 9.2 Tracking Follower Progress

Two dictionaries track each follower:

```python
self.next_index = {identifier: len(self.log) for identifier in self.config}
self.match_index = {identifier: None for identifier in self.config}
```

- `next_index[i]`: Index of next entry to send to follower i
- `match_index[i]`: Highest index known replicated on follower i

### 9.3 Creating AppendEntryRequest

`create_append_entries_arguments` builds the request:

```python
def create_append_entries_arguments(self, target: int) -> Tuple[...]:
    next_index = self.next_index[target]
    previous_index = next_index - 1
    previous_term = self.log[previous_index].term if ... else -1

    return (
        self.current_term,
        previous_index,
        previous_term,
        self.log[next_index:],  # entries to replicate
        self.commit_index,
    )
```

### 9.4 Handling AppendEntryRequest (Follower Side)

`handle_append_entries_request`:
1. Update term if leader's term is higher
2. Call `raftlog.append_entries` to update log
3. Update own `commit_index` based on leader's
4. Return success/failure response

### 9.5 Handling AppendEntryResponse (Leader Side)

`handle_append_entries_response`:
- If success: Update `next_index` and `match_index` for follower
- If failure: Decrement `next_index` and retry with earlier entries

The retry mechanism reconciles divergent logs.

### 9.6 Log Reconciliation in Action

Walking through Figure 7 scenarios:
- Follower missing entries: Leader backs up until finding match
- Follower has extra entries: Overwritten by leader's entries
- Follower has conflicting entries: Deleted and replaced

### 9.7 Advancing the Commit Index

An entry is committed when replicated on a majority. The leader finds the median `match_index`:

```python
def update_indexes(self, target: int, entries_length: int) -> None:
    # ... update next_index and match_index ...

    non_null_match_index_count, potential_commit_index = self.get_index_metrics()

    if non_null_match_index_count >= self.count_majority():
        if self.log[potential_commit_index].term == self.current_term:
            self.commit_index = potential_commit_index
```

### 9.8 The Commit Index Safety Rule

Why the check `log[N].term == currentTerm`? Without it, a leader could commit entries from a previous term that might be overwritten. This is the Figure 8 scenario from the paper. The test `test_commit_with_requirement` demonstrates this.

### 9.9 Propagating Commit Index

Followers learn the commit index from the leader's `AppendEntryRequest.commit_index`. They update their own commit index accordingly:

```python
if commit_index > self.commit_index:
    self.commit_index = min(commit_index, len(self.log) - 1)
```

## Conclusion

The leader replicates entries by sending `AppendEntryRequest` messages and tracking progress with `nextIndex` and `matchIndex`. Failed appends trigger retries with earlier log portions until logs match. Entries are committed when replicated on a majority, but only entries from the current term advance the commit index (preventing the Figure 8 anomaly). Followers learn the commit index through heartbeats.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Leader heartbeats
- `next_index` and `match_index` management
- `create_append_entries_arguments`
- `handle_append_entries_request` (follower)
- `handle_append_entries_response` (leader)
- Log reconciliation / backtracking
- Commit index advancement
- Figure 8 safety rule (`log[N].term == currentTerm`)
- Commit index propagation to followers

**Back-references**:
- Chapter 3 introduced `append_entries` called by follower handler
- Chapter 6 introduced `next_index`, `match_index`, `commit_index` attributes
- Chapter 7 introduced `AppendEntryRequest/Response` message types
- Chapter 8 showed leader initialization after election

**Forward dependencies**:
- Chapter 11 shows heartbeat timing in the server
