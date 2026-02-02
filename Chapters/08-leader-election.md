# Chapter 8: Leader Election

## Introduction

This chapter covers how Raft elects a leader. When a follower times out without hearing from a leader, it becomes a candidate and solicits votes. If it receives a majority, it becomes leader. The election mechanism ensures at most one leader per term and prevents stale leaders from disrupting the cluster.

## Sections

### 8.1 Election Triggers

A follower becomes a candidate when:
1. Election timeout elapses
2. No `AppendEntryRequest` received from a leader
3. No vote granted to another candidate

The `change_state_on_timeout` function creates the `RoleChange` message.

### 8.2 Starting an Election

When transitioning to candidate:
1. Increment `current_term`
2. Vote for self (`voted_for = self.identifier`)
3. Initialize `current_votes` with self-vote
4. Send `RequestVoteRequest` to all other nodes

```python
def handle_candidate_solicitation(self, ...) -> List[raftmessage.Message]:
    for follower in followers:
        message = raftmessage.RequestVoteRequest(
            self.identifier,
            follower,
            self.current_term,
            len(self.log) - 1,
            previous_term,
        )
        messages.append(message)
```

### 8.3 The RequestVoteRequest Handler

How followers decide whether to grant a vote in `handle_request_vote_request`:

1. Reject if candidate's term < own term
2. Reject if already voted for someone else this term
3. Reject if candidate's log is less up-to-date
4. Otherwise, grant vote and record `voted_for`

### 8.4 Log Comparison for Voting

"Up-to-date" means:
- Higher term on last entry wins
- If terms equal, longer log wins

This ensures the elected leader has all committed entries.

### 8.5 Counting Votes

`handle_request_vote_response` tracks received votes:

```python
if success:
    self.current_votes[source] = target

    if self.has_won_election():
        # Transition to leader
```

`has_won_election` checks if `count_self_votes() >= count_majority()`.

### 8.6 Becoming Leader

Upon winning:
1. Transition from candidate to leader
2. Initialize `next_index` (all entries at log end)
3. Initialize `match_index` (nothing confirmed yet)
4. Send immediate heartbeat to establish authority

### 8.7 Split Votes and Re-election

If no candidate gets a majority, the term ends without a leader. Randomized timeout ensures candidates don't all restart simultaneously.

### 8.8 Stepping Down

A candidate becomes follower if:
- It sees an `AppendEntryRequest` from a leader with >= term
- It sees any message with a higher term

## Conclusion

Leader election ensures exactly one leader per term. Candidates solicit votes, voters check term and log freshness, and the first to reach majority wins. Randomized timeouts prevent split-vote deadlocks. The elected leader is guaranteed to have all committed entries, preserving safety.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Election timeout trigger
- `handle_candidate_solicitation`
- `handle_request_vote_request` and voting criteria
- Log comparison (term, then length)
- `handle_request_vote_response` and vote counting
- `has_won_election` and majority calculation
- Split votes and randomized timeout

**Back-references**:
- Chapter 5 introduced role transitions (follower → candidate → leader)
- Chapter 6 introduced `votedFor` and `currentVotes` state
- Chapter 7 introduced `RequestVoteRequest/Response` message types

**Forward dependencies**:
- Chapter 9 shows what the leader does after election
- Chapter 11 implements the actual timeout mechanism
