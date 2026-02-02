# Chapter 6: Log Replication

Log replication is how the leader keeps follower logs synchronized. This chapter explains the protocol in detail: how the leader tracks follower progress with `nextIndex` and `matchIndex`, what happens when replication fails, and the rules for advancing `commitIndex`.

This is where Raft's safety guarantees become concrete. The commit index only advances when a majority has replicated an entry. The leader only commits entries from its current term. These rules prevent committed entries from being lost, even across leader failures.

## The Leader's Responsibility

When a server becomes leader, it takes responsibility for the cluster's log. Clients send commands to the leader; the leader appends them to its log and replicates to followers. Once a majority of servers have the entry, it's committed—guaranteed never to be lost.

The leader maintains two data structures to track follower progress:

```python
case raftrole.Operation.INITIALIZE:
    self.next_index = {
        identifier: len(self.log) for identifier in self.config
    }

case raftrole.Operation.INITIALIZE:
    self.match_index = {identifier: None for identifier in self.config}
    self.match_index[self.identifier] = len(self.log) - 1
```

When a new leader is elected:
- `next_index` starts at `len(log)` for all servers—optimistically assuming everyone is caught up
- `match_index` starts at `None` for other servers (we don't know their state) but `len(log) - 1` for itself (the leader knows its own log)

## nextIndex and matchIndex

These two dictionaries track different things:

**nextIndex[server]**: The index of the next entry to send to this server. This is optimistic—we start high and decrement on failure. Think of it as "where to resume sending."

**matchIndex[server]**: The highest entry known to be replicated on this server. This is conservative—we only update it on successful responses. Think of it as "how far we're sure they've got."

The relationship: if a follower's `matchIndex` is M, then `nextIndex` should be M+1 (send the next entry after what they have).

Why two separate trackers? Because Raft needs to be conservative about what's committed (safety) but can be optimistic about what to send (performance). If we only tracked `matchIndex`, we'd have to probe followers one entry at a time to find their log state. With `nextIndex`, we can guess high and correct downward on failures.

## The Heartbeat Flow

The leader sends periodic heartbeats via `handle_leader_heartbeat`:

```python
def handle_leader_heartbeat(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:

    messages: List[raftmessage.Message] = []

    for follower in followers:
        message = raftmessage.AppendEntryRequest(
            self.identifier,
            follower,
            *self.create_append_entries_arguments(follower),
        )
        messages.append(message)

    return messages
```

For each follower, it builds an `AppendEntryRequest` with the entries starting at `nextIndex[follower]`. If the follower is caught up, `entries` is empty—a pure heartbeat.

The `create_append_entries_arguments` helper builds the request parameters:

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
        self.log[next_index:],  # Entries from nextIndex onward
        self.commit_index,
    )
```

The `previous_index` and `previous_term` are for the consistency check—they describe the entry that should immediately precede the new entries in the follower's log.

## Handling Append Entry Responses

When a follower responds, `handle_append_entries_response` processes it:

```python
def handle_append_entries_response(
    self,
    source: int,
    target: int,
    current_term: int,
    success: bool,
    entries_length: int,
) -> List[raftmessage.Message]:

    # State change check (might step down if higher term)
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    if self.role != raftrole.Role.LEADER:
        return []

    if success:
        self.update_indexes(source, entries_length)
        self.has_followers = True
        return []

    # Failure: decrement nextIndex, retry
    self.next_index[source] = self.next_index[source] - 1

    return [
        raftmessage.AppendEntryRequest(
            target,
            source,
            *self.create_append_entries_arguments(source),
        )
    ]
```

On **success**: Update the indexes and note that we have responsive followers (for the `has_followers` check).

On **failure**: The follower's log doesn't match at `previous_index`. Decrement `nextIndex` for this follower and retry with earlier entries. Eventually we find where the logs agree.

The retry is immediate—we don't wait for the next heartbeat. This speeds up convergence when logs have diverged significantly.

## The Follower's Perspective

From the follower's side, `handle_append_entries_request` processes the leader's message:

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

    # State change (might update term, convert to follower)
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.LEADER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.AppendEntryResponse(
                target, source, self.current_term, False, len(entries)
            )
        ]

    # Try to append
    success = raftlog.append_entries(
        self.log, previous_index, previous_term, entries
    )

    # Update commit index based on leader's value
    if commit_index > self.commit_index:
        self.commit_index = min(commit_index, len(self.log) - 1)

    return [
        raftmessage.AppendEntryResponse(
            target, source, self.current_term, success, len(entries)
        )
    ]
```

The follower calls `raftlog.append_entries` (from Chapter 2) to validate and append. If the consistency check fails, `append_entries` returns False and the follower responds with `success=False`.

The commit index update is important: followers learn what's committed through the leader's heartbeats. They advance their `commit_index` to match the leader's, but never past their own log length.

## Advancing commitIndex

The leader advances its commit index in `update_indexes`:

```python
def update_indexes(self, target: int, entries_length: int) -> None:
    self.next_index[target] += entries_length
    self.match_index[target] = self.next_index[target] - 1

    non_null_match_index_count, potential_commit_index = self.get_index_metrics()

    # Need majority to commit
    if non_null_match_index_count < self.count_majority():
        return None

    # Critical safety check: only commit current-term entries
    update_commit_index = (
        len(self.log) > 0
        and self.log[potential_commit_index].term == self.current_term
    )

    if update_commit_index or self.experimental_mode:
        self.commit_index = potential_commit_index
```

The `get_index_metrics` helper finds the median of non-None `matchIndex` values. If a majority of servers have an entry, it's at or below this median.

The critical check is `self.log[potential_commit_index].term == self.current_term`. Leaders only commit entries from their own term. This is the key to Raft's safety guarantee.

## The Figure 8 Problem

Why can't leaders commit entries from previous terms? The Raft paper's Figure 8 shows a scenario where doing so would be unsafe:

1. Leader S1 in term 2 replicates an entry to S1 and S2 (majority), but crashes before committing
2. S5 becomes leader in term 3, appends different entries
3. S1 becomes leader in term 4
4. If S1 commits the term-2 entry (it's on a majority), then crashes...
5. S5 can become leader in term 5 and overwrite the "committed" entry

The problem is that the term-2 entry wasn't replicated by the term-4 leader. A later leader from term 5 could have a log that doesn't include it but still gets elected (if it has other entries that make its log "at least as up-to-date").

The solution: **only commit through current-term entries**. When a leader commits an entry from its own term, all previous entries are implicitly committed. The term-4 leader can't commit the term-2 entry directly, but once it adds and commits a term-4 entry, everything before it is safe.

## Testing Replication: Figure 7 Scenarios

The tests in `test_raftstate.py` reproduce Figure 7 from the Raft paper—various ways follower logs can diverge:

```
Leader (term 6):            [1,1,1,4,4,5,5,6,6,6]

(a) Missing last entry:     [1,1,1,4,4,5,5,6,6]
(b) Missing last 6 entries: [1,1,1,4]
(c) Extra entry:            [1,1,1,4,4,5,5,6,6,6,6]
(d) Extra entries term 7:   [1,1,1,4,4,5,5,6,6,6,7,7]
(e) Diverged at index 5:    [1,1,1,4,4,4,4]
(f) Completely different:   [1,1,1,2,2,2,3,3,3,3,3]
```

The tests verify that the leader eventually brings all followers into sync:

```python
def test_handle_message_b(paper_log, logs_by_identifier):
    # Follower missing last 6 entries
    leader_state, follower_state, _, request = init_raft_states(
        paper_log, logs_by_identifier["b"], None
    )

    # 6 rounds of failure before success
    for i in range(6):
        response = follower_state.handle_message(request[0])
        assert not response[0].success
        assert leader_state.next_index[2] == 10 - i
        request = leader_state.handle_message(response[0])

    # Finally succeeds
    response = follower_state.handle_message(request[0])
    assert response[0].success
    assert response[0].entries_length == 6
```

The leader starts optimistically at index 10, fails, decrements to 9, fails, decrements to 8, and so on until it finds where the logs agree (index 4). Then it sends 6 entries to catch the follower up.

## The Consensus Test

The `test_consensus` test shows a three-server cluster reaching agreement:

```python
def test_consensus(paper_log, logs_by_identifier):
    leader_state, follower_a_state, follower_b_state, request = init_raft_states(
        paper_log, logs_by_identifier["a"], logs_by_identifier["b"]
    )

    # Initially: commit_index = -1

    # After follower A catches up (1 retry):
    # match_index = {1: 9, 2: 9, 3: None}
    # commit_index = 9 (majority!)

    # After follower B catches up (6 retries):
    # match_index = {1: 9, 2: 9, 3: 9}
    # commit_index = 9

    # Send heartbeat to update followers' commit_index
    request = leader_state.handle_leader_heartbeat(followers=[2, 3])
    follower_a_state.handle_message(request[0])
    follower_b_state.handle_message(request[1])

    assert follower_a_state.commit_index == 9
    assert follower_b_state.commit_index == 9
```

The leader commits after getting a response from follower A (2 out of 3 is majority). Follower B takes longer to sync, but the commit is already safe.

## Conclusion

Log replication is optimistic but self-correcting. The leader guesses where followers are (`nextIndex`), sends entries, and adjusts on failure. The `matchIndex` tracks confirmed progress; the commit rules ensure safety.

The key insight is the separation of concerns: `nextIndex` can be wrong (just affects performance), but `matchIndex` and `commitIndex` must be correct (affects safety). The leader only advances `commitIndex` when entries are confirmed on a majority, and only for entries from its current term.

The next chapter covers the other half of Raft: how leaders get elected in the first place.
