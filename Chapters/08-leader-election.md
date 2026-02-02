# Chapter 8: Leader Election

## Introduction

This chapter covers how Raft elects a leader. When a follower times out without hearing from a leader, it becomes a candidate and solicits votes. If it receives a majority, it becomes leader. The election mechanism ensures at most one leader per term and prevents stale leaders from disrupting the cluster.

## 8.1 Election Triggers

A follower becomes a candidate when three conditions are met:

1. The election timeout elapses
2. No `AppendEntryRequest` received from a leader
3. No vote granted to another candidate

The `change_state_on_timeout` function checks the current role and produces the appropriate message:

```python
def change_state_on_timeout(state: RaftState) -> raftmessage.Message:
    match state.role:
        case raftrole.Role.FOLLOWER:
            return raftmessage.RoleChange(
                state.identifier,
                state.identifier,
                raftrole.Role.FOLLOWER,
                raftrole.Role.CANDIDATE,
            )

        case raftrole.Role.CANDIDATE:
            state.current_term += 1
            return raftmessage.RunElection(
                state.identifier, state.identifier, state.create_followers_list()
            )

        # ...
```

For a follower, this triggers a role change to candidate. For a candidate (whose election timed out without winning), it starts a new election with an incremented term.

## 8.2 Starting an Election

When a follower becomes a candidate, several things happen:

1. **Increment term**: The new candidate moves to a fresh term
2. **Vote for self**: The candidate votes for itself
3. **Initialize vote tracking**: Set up `current_votes` with self-vote
4. **Send vote requests**: Ask all other nodes for votes

The `handle_role_change` method initiates this:

```python
def handle_role_change(
    self, source: int, target: int, from_role: raftrole.Role, to_role: raftrole.Role
) -> List[raftmessage.Message]:
    assert self.role == from_role

    match (from_role, to_role):
        case (raftrole.Role.FOLLOWER, raftrole.Role.CANDIDATE):
            self.change_role(from_role, to_role)
            return [
                raftmessage.RunElection(
                    self.identifier, self.identifier, self.create_followers_list()
                )
            ]
```

The returned `RunElection` message triggers `handle_candidate_solicitation`:

```python
def handle_candidate_solicitation(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:
    if self.role != raftrole.Role.CANDIDATE:
        raise Exception("Not able to solicit votes when not candidate.")

    followers = followers or self.create_followers_list()
    messages: List[raftmessage.Message] = []

    previous_term = self.log[-1].term if len(self.log) > 0 else -1

    for follower in followers:
        message = raftmessage.RequestVoteRequest(
            self.identifier,
            follower,
            self.current_term,
            len(self.log) - 1,
            previous_term,
        )
        messages.append(message)

    return messages
```

Each `RequestVoteRequest` contains:
- `current_term`: The candidate's term
- `last_log_index`: Index of the candidate's last log entry
- `last_log_term`: Term of that entry

## 8.3 The RequestVoteRequest Handler

When a node receives a vote request, `handle_request_vote_request` decides whether to grant the vote:

```python
def handle_request_vote_request(
    self,
    source: int,
    target: int,
    current_term: int,
    last_log_index: int,
    last_log_term: int,
) -> List[raftmessage.Message]:
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.CANDIDATE, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # If not follower, reject
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.RequestVoteResponse(target, source, False, self.current_term)
        ]

    # Check term
    if current_term < self.current_term:
        success = False

    # Check log length
    elif last_log_index < len(self.log) - 1:
        success = False

    # Check last entry term
    elif len(self.log) > 0 and last_log_term < self.log[-1].term:
        success = False

    else:
        # Check if already voted for someone else
        if self.voted_for is not None and self.voted_for != source:
            success = False
        else:
            if self.voted_for is None:
                self.voted_for = source
            success = True

    return [
        raftmessage.RequestVoteResponse(target, source, success, self.current_term)
    ]
```

The voting rules, in order:

1. **Role check**: Only followers can grant votes
2. **Term check**: Reject if candidate's term < voter's term
3. **Log length check**: Reject if candidate's log is shorter
4. **Log term check**: Reject if candidate's last entry has older term
5. **Already voted**: Reject if already voted for different candidate this term

## 8.4 Log Comparison for Voting

The log comparison rules ensure that the elected leader has all committed entries. "Up-to-date" is defined by comparing the last entry:

```
Candidate A: [..., (term=3)]
Candidate B: [..., (term=2)]
→ A wins (higher term on last entry)

Candidate A: [..., (term=2), (term=2), (term=2)]
Candidate B: [..., (term=2)]
→ A wins (same term, longer log)
```

Why these rules work: A committed entry must have been replicated on a majority. Any new leader must have received votes from a majority, which overlaps with the replication majority. The log comparison ensures that within that overlap, at least one voter had the committed entry, and it would only vote for a candidate that also has it.

## 8.5 Counting Votes

When a candidate receives a `RequestVoteResponse`, it updates its vote tracking:

```python
def handle_request_vote_response(
    self,
    source: int,
    target: int,
    success: bool,
    current_term: int,
) -> List[raftmessage.Message]:
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    if self.role != raftrole.Role.CANDIDATE:
        return []

    if success:
        assert self.current_votes is not None
        self.current_votes[source] = target

        if self.has_won_election():
            state_change = raftrole.enumerate_state_change(
                raftrole.Role.ELECTION_COMMISSION,
                self.current_term,
                self.role,
                self.current_term,
            )
            self.implement_state_change(state_change)

            return [
                raftmessage.UpdateFollowers(
                    self.identifier, self.identifier, self.create_followers_list()
                )
            ]

    return []
```

The `has_won_election` check:

```python
def has_won_election(self) -> bool:
    return self.count_self_votes() >= self.count_majority()

def count_self_votes(self) -> int:
    assert self.current_votes is not None
    return len(
        [
            identifier
            for identifier in self.current_votes.values()
            if identifier == self.identifier
        ]
    )

def count_majority(self) -> int:
    return 1 + len(self.config) // 2
```

For a 3-node cluster, majority is 2. The candidate already has its own vote, so it needs one more.

## 8.6 Becoming Leader

Upon winning the election, the candidate:

1. Transitions to leader role
2. Initializes `next_index` (optimistically set to log end for all followers)
3. Initializes `match_index` (nothing confirmed yet)
4. Sends immediate heartbeat via `UpdateFollowers`

The `UpdateFollowers` message triggers `handle_leader_heartbeat`:

```python
def handle_leader_heartbeat(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:
    if self.role != raftrole.Role.LEADER:
        raise Exception("Not able to generate leader heartbeat when not leader.")

    followers = followers or self.create_followers_list()
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

This sends `AppendEntryRequest` to all followers, establishing authority.

## 8.7 Split Votes and Re-election

What if no candidate gets a majority? This happens when multiple candidates start simultaneously and split the votes.

```
Term 5:
  Node 1 (candidate): votes from [1, 2] → 2 votes
  Node 2 (candidate): votes from [3]   → 1 vote
  Node 3 (follower):  voted for Node 2

Neither reaches majority (needs 2 for 3-node cluster)
```

When the election timeout expires without a winner, `change_state_on_timeout` starts a new election:

```python
case raftrole.Role.CANDIDATE:
    state.current_term += 1
    return raftmessage.RunElection(
        state.identifier, state.identifier, state.create_followers_list()
    )
```

To prevent repeated split votes, each node uses randomized timeout:

```python
def timeout(self) -> None:
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)
```

Different followers wake up at different times, so one usually wins before others start their elections.

## 8.8 Stepping Down

A candidate becomes follower if it discovers it lost:

**Sees higher term**: Any message with a higher term causes step-down

```python
if source_term > target_term:
    current_term = source_term
    voted_for = Operation.RESET_TO_NONE
    role_change = (Role.CANDIDATE, Role.FOLLOWER)
```

**Sees current leader**: An `AppendEntryRequest` with equal term means another candidate won

```python
case (Role.LEADER, Role.CANDIDATE):
    if source_term == target_term:
        role_change = (Role.CANDIDATE, Role.FOLLOWER)
```

## 8.9 Election Safety

Raft guarantees at most one leader per term through two mechanisms:

1. **Each node votes once per term**: Once `voted_for` is set, it doesn't change until the term changes

2. **Majority required**: A candidate needs votes from more than half the nodes. Two majorities must overlap, so two candidates can't both win.

## Conclusion

Leader election ensures exactly one leader per term. Followers become candidates on timeout, candidates solicit votes, and voters check both term and log freshness before granting votes. The first candidate to reach majority wins and immediately establishes authority through heartbeats. Randomized timeouts prevent split-vote deadlocks. The log comparison rules ensure the elected leader has all committed entries, preserving Raft's safety guarantees.
