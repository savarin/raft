# Chapter 7: Leader Election

## What This Chapter Covers

When a leader fails or becomes unreachable, the cluster must elect a new one. This chapter explains the election protocol: how followers become candidates, how votes are requested and granted, and the safety constraints that prevent split-brain scenarios.

Elections are Raft's availability mechanism. Log replication keeps the system consistent; elections keep it running when servers fail. Understanding elections means understanding timeouts, vote counting, and the "at least as up-to-date" rule that ensures the new leader has all committed entries.

## Sections

### When Elections Happen

Followers expect periodic heartbeats. No heartbeat within the timeout means the leader is gone (or unreachable). The timeout triggers a transition to candidate. Random jitter prevents synchronized elections.

### Becoming a Candidate

`change_state_on_timeout` for followers. Increment term, vote for self, reset election timer. The state changes encoded in `enumerate_state_change(TIMER, ...)`. Why voting for yourself is automatic.

### Requesting Votes

`handle_candidate_solicitation` broadcasts `RequestVoteRequest` to all other servers. The request includes: current term, and the candidate's log state (last log index and last log term).

### Granting Votes

`handle_request_vote_request` on the receiving server. The checks: Is the term high enough? Have I already voted this term? Is the candidate's log at least as up-to-date as mine? The "at least as up-to-date" comparison: higher last term wins; if terms equal, longer log wins.

### Why Log Freshness Matters

The Election Safety guarantee: the leader has all committed entries. If a candidate's log is behind, it might not have committed entries. Voters reject such candidates. This is how committed entries survive leader changes.

### Counting Votes

`handle_request_vote_response` tallies votes. `count_self_votes` and `has_won_election`. When a majority votes yes, the candidate becomes leader via `ELECTION_COMMISSION` pseudo-role. Immediate transition, immediate heartbeat.

### Split Votes and Retries

What happens when no candidate gets a majority: election timeout, term increments, new election. Random timeouts make split votes unlikely to persist. Liveness, not safety—the system makes progress eventually.

### Leader Stepping Down

The other direction: `CONSTITUTION` pseudo-role. If a leader sends heartbeats but gets no responses, it steps down. Why this matters: a leader partitioned from the cluster shouldn't think it's still leader.

### Testing Election Scenarios

How to test elections without real timeouts: directly invoke `change_state_on_timeout`, feed vote messages to state machines, verify transitions. The importance of testing the "at least as up-to-date" logic.

## Conclusion

Elections balance liveness and safety. Random timeouts make progress likely. Vote restrictions make progress safe—only candidates with complete logs can win. The implementation encodes these rules in `handle_request_vote_request`'s validation checks and `raftrole.enumerate_state_change`'s transition logic. Together they ensure the cluster always has a valid leader—or is working to elect one.
