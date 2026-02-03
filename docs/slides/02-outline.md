# Slide Outline: Understanding Raft

**Target:** 20 minutes | **Estimated slides:** 22 | **Pace:** ~55 seconds/slide average

## Section Structure

### Opening (3 slides, ~2 min)
1. Title slide
2. The problem: distributed systems need agreement
3. Raft's core insight: understandability as a design goal

### Part 1: The Foundation (4 slides, ~4 min)
4. Three roles: Leader, Candidate, Follower
5. Terms: logical clocks for distributed time
6. The log: ordered sequence of commands
7. The invariant: one leader per term, leader's log is truth

*Code needed: Role enum, term handling*

### Part 2: Leader Election (6 slides, ~6 min)
8. Election trigger: follower timeout
9. Becoming a candidate: increment term, vote for self
10. Requesting votes: what makes a valid candidate?
11. Granting votes: the safety constraints
12. Winning: majority means authority
13. The split vote problem and randomized timeouts

*Code needed: vote request handling, vote granting logic*

### Part 3: Log Replication (6 slides, ~6 min)
14. Leader receives client request
15. AppendEntries RPC: the replication message
16. Consistency check: previous index and term
17. Handling conflicts: leader always wins
18. Commit point: when is an entry safe?
19. The safety guarantee: committed entries survive

*Code needed: append_entries function, commit advancement*

### Closing (3 slides, ~2 min)
20. What we didn't cover (membership changes, snapshots)
21. The implementation: 2,400 lines of Python
22. Questions / Resources

---

## Timing Budget

| Section | Slides | Minutes | Notes |
|---------|--------|---------|-------|
| Opening | 3 | 2 | Set context quickly |
| Foundation | 4 | 4 | Key concepts, pace matters |
| Election | 6 | 6 | Core algorithm, show code |
| Replication | 6 | 6 | Core algorithm, show code |
| Closing | 3 | 2 | Wrap up, resources |
| **Total** | **22** | **20** | |

## Section Dividers

Decision: **No explicit section divider slides.** At 22 slides, dividers would add overhead. Instead, use visual cues:
- `<!-- _class: invert -->` for Part 1/2/3 opening slides
- Clear headline transitions

## Code Examples Needed

| Slide | Source | Purpose |
|-------|--------|---------|
| 4 | `raftrole.py:Role` | Show the three roles |
| 5 | `raftstate.py:handle_*` | Term comparison pattern |
| 10 | `raftmessage.py:RequestVoteRequest` | Vote request structure |
| 11 | `raftstate.py:handle_request_vote_request` | Vote granting logic |
| 15 | `raftmessage.py:AppendEntryRequest` | Replication message structure |
| 16-17 | `raftlog.py:append_entries` | Consistency check + conflict resolution |
| 18 | `raftstate.py` | Commit index advancement |

## Diagrams Needed

| Slide | Type | Content |
|-------|------|---------|
| 7 | ASCII | Three servers, leader sending to followers |
| 8 | ASCII | Timeline: follower timeout → candidate |
| 12 | ASCII | Election: 3 servers, vote flow |
| 14-15 | ASCII | Log replication flow |
