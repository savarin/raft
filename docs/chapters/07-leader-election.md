# Chapter 7: Leader Election

When a leader fails or becomes unreachable, the cluster must elect a new one. This chapter explains the election protocol: how followers become candidates, how votes are requested and granted, and the safety constraints that prevent split-brain scenarios.

Elections are Raft's availability mechanism. Log replication keeps the system consistent; elections keep it running when servers fail. Understanding elections means understanding timeouts, vote counting, and the "at least as up-to-date" rule that ensures the new leader has all committed entries.

## When Elections Happen

Followers expect periodic heartbeats from the leader. If no heartbeat arrives within the timeout period, the follower assumes the leader has failed.

The timeout handling in `change_state_on_timeout`:

```python
case raftrole.Role.FOLLOWER:
    return raftmessage.RoleChange(
        state.identifier,
        state.identifier,
        raftrole.Role.FOLLOWER,
        raftrole.Role.CANDIDATE,
    )
```

A follower that times out generates a `RoleChange` message to transition itself to candidate.

The timeout value is important. The implementation uses different timeouts for different roles:

```python
# In RaftServer
timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT
```

Leaders check quickly (3 seconds); followers wait longer (6 seconds). This asymmetry gives the leader time to send heartbeats before followers give up.

Additionally, follower timeouts include random jitter:

```python
if self.state.role == raftrole.Role.FOLLOWER:
    time.sleep(random.random() * TIMEOUT)
```

This prevents synchronized elections—if all followers time out simultaneously and become candidates, they might split the vote. Random jitter spreads out the transitions.

## Becoming a Candidate

When a follower becomes a candidate, several things happen (via `enumerate_state_change` with `TIMER` source):

```python
case (Role.TIMER, Role.FOLLOWER):
    current_term = target_term + 1      # Increment term
    voted_for = Operation.INITIALIZE    # Vote for self
    role_change = (Role.FOLLOWER, Role.CANDIDATE)
```

And `evaluate_operations` initializes vote tracking:

```python
case (Role.FOLLOWER, Role.CANDIDATE):
    current_votes = Operation.INITIALIZE
```

The candidate votes for itself immediately. In `implement_state_change`:

```python
case raftrole.Operation.INITIALIZE:
    self.voted_for = self.identifier
    self.current_votes = {identifier: None for identifier in self.config}
    self.current_votes[self.identifier] = self.identifier
```

The candidate starts with one vote (its own). It needs `count_majority() - 1` more votes to win.

## Requesting Votes

After becoming a candidate, `handle_role_change` triggers vote solicitation:

```python
case (raftrole.Role.FOLLOWER, raftrole.Role.CANDIDATE):
    self.change_role(from_role, to_role)
    return [
        raftmessage.RunElection(
            self.identifier, self.identifier, self.create_followers_list()
        )
    ]
```

This generates a `RunElection` message, which `handle_candidate_solicitation` processes:

```python
def handle_candidate_solicitation(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:

    messages: List[raftmessage.Message] = []
    previous_term = self.log[-1].term if len(self.log) > 0 else -1

    for follower in followers:
        message = raftmessage.RequestVoteRequest(
            self.identifier,
            follower,
            self.current_term,
            len(self.log) - 1,      # last_log_index
            previous_term,           # last_log_term
        )
        messages.append(message)

    return messages
```

The request includes the candidate's log information: the index and term of its last entry. Voters use this to decide if the candidate's log is "at least as up-to-date."

## Granting Votes

When a server receives `RequestVoteRequest`, it must decide whether to grant the vote. The logic in `handle_request_vote_request`:

```python
def handle_request_vote_request(
    self,
    source: int,
    target: int,
    current_term: int,
    last_log_index: int,
    last_log_term: int,
) -> List[raftmessage.Message]:

    # Update term if needed
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.CANDIDATE, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # Only followers can vote
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.RequestVoteResponse(
                target, source, False, self.current_term
            )
        ]

    # Check 1: Candidate must have term >= our term
    if current_term < self.current_term:
        success = False

    # Check 2: Candidate's log must be at least as long
    elif last_log_index < len(self.log) - 1:
        success = False

    # Check 3: Candidate's last entry term must be >= our last entry term
    elif len(self.log) > 0 and last_log_term < self.log[-1].term:
        success = False

    # Check 4: Haven't voted for someone else this term
    else:
        if self.voted_for is not None and self.voted_for != source:
            success = False
        else:
            if self.voted_for is None:
                self.voted_for = source
            success = True

    return [
        raftmessage.RequestVoteResponse(
            target, source, success, self.current_term
        )
    ]
```

Four conditions must all be true:

1. **Term check**: The candidate's term must be at least as high as ours
2. **Log length**: The candidate's log must be at least as long
3. **Log term**: The candidate's last entry must have term >= our last entry's term
4. **Vote availability**: We haven't already voted for a different candidate this term

Conditions 2 and 3 together form the "at least as up-to-date" rule. A candidate with a shorter log or older last entry might be missing committed entries.

## Why Log Freshness Matters

The Election Safety property guarantees that any elected leader has all committed entries. The log comparison enforces this.

Consider: an entry is committed when it's replicated on a majority. For a candidate to win, it needs votes from a majority. These majorities must overlap—there's at least one server in both.

That overlapping server has the committed entry. It will only vote for a candidate whose log includes that entry (or is more recent). So any winner must have all committed entries.

The comparison prioritizes term over length:

```python
# Check term first
elif len(self.log) > 0 and last_log_term < self.log[-1].term:
    success = False
# Then check length
elif last_log_index < len(self.log) - 1:
    success = False
```

A candidate with last entry term 5 beats one with term 4, even if the term-4 candidate has a longer log. Terms are more authoritative than length.

## Counting Votes

When a candidate receives `RequestVoteResponse`, it updates its vote count:

```python
def handle_request_vote_response(
    self,
    source: int,
    target: int,
    success: bool,
    current_term: int,
) -> List[raftmessage.Message]:

    # State change check
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    if self.role != raftrole.Role.CANDIDATE:
        return []

    if success:
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
```

Once a candidate has majority votes, it becomes leader via the `ELECTION_COMMISSION` pseudo-role. It immediately sends heartbeats to establish authority.

## Split Votes and Retries

What if no candidate gets a majority? Each candidate's election timeout fires, it increments its term, and tries again:

```python
case raftrole.Role.CANDIDATE:
    state.current_term += 1
    return raftmessage.RunElection(
        state.identifier, state.identifier, state.create_followers_list()
    )
```

Random timeouts make persistent split votes unlikely. If two candidates tie in term 5, they both time out—but at different times due to jitter. One starts term 6 first, likely winning before the other even begins.

This is a liveness property: the system eventually makes progress. It might take a few election rounds, but eventually someone wins.

## Leader Stepping Down

Leaders can also lose their position. If a leader sends heartbeats but gets no responses:

```python
case raftrole.Role.LEADER:
    assert state.has_followers is not None

    if not state.has_followers:
        return raftmessage.RoleChange(
            state.identifier,
            state.identifier,
            raftrole.Role.LEADER,
            raftrole.Role.FOLLOWER,
        )

    state.has_followers = False
    return raftmessage.UpdateFollowers(
        state.identifier, state.identifier, state.create_followers_list()
    )
```

Each heartbeat round sets `has_followers = False`. Responses set it back to `True`. If the next timeout fires with the flag still `False`, the leader steps down.

This handles network partitions. A leader isolated from the rest of the cluster shouldn't keep acting as leader—it can't commit anything anyway. Stepping down lets it rejoin properly when the partition heals.

## Testing Election Scenarios

The tests verify election logic without real timeouts. From `test_raftstate.py`:

```python
def test_handle_vote_request(logs_by_identifier):
    # Candidate with log from Figure 7c
    candidate_state, _ = init_raft_state(
        1, logs_by_identifier["c"], raftrole.Role.FOLLOWER, 6
    )
    candidate_state.change_role(raftrole.Role.FOLLOWER, raftrole.Role.CANDIDATE)
    request = candidate_state.handle_candidate_solicitation()

    # Voter with shorter log (Figure 7a) grants vote
    follower_a_state, _ = init_raft_state(
        1, logs_by_identifier["a"], raftrole.Role.FOLLOWER, 6
    )
    response = follower_a_state.handle_message(request[0])
    assert response[0].success

    # Voter with longer log + higher term (Figure 7d) denies vote
    follower_d_state, _ = init_raft_state(
        2, logs_by_identifier["d"], raftrole.Role.FOLLOWER, 6
    )
    response = follower_d_state.handle_message(request[1])
    assert not response[0].success  # Log has term 7 entries
```

The test shows that a candidate can get votes from servers with "behind" logs but not from servers with "ahead" logs.

## The Full Election Flow

Putting it together:

1. Follower times out → becomes candidate, increments term, votes for self
2. Candidate sends `RequestVoteRequest` to all other servers
3. Each server decides based on term and log freshness
4. Candidate collects responses, counts votes
5. If majority → become leader, send immediate heartbeats
6. If no majority and timeout → increment term, try again

The invariants:
- At most one leader per term (each server votes at most once per term)
- Any leader has all committed entries (log comparison ensures overlap)
- Eventually some candidate wins (random timeouts break ties)

## Conclusion

Elections balance safety and liveness. The log comparison ensures any winner has all committed entries—safety. Random timeouts ensure elections eventually succeed—liveness.

The implementation encodes these rules in `handle_request_vote_request` (the validation) and `handle_request_vote_response` (the counting). The `ELECTION_COMMISSION` pseudo-role signals victory; the candidate immediately transitions to leader and starts replicating.

Together with log replication (Chapter 6), elections form the complete Raft algorithm. The next chapter shows how these pieces run in practice: networks, timers, and the event loop.
