# Storyboard: Understanding Raft

Reference: [01-proposal.md](01-proposal.md) | [02-outline.md](02-outline.md)

---

## Opening (3 slides)

### Slide 1: Title
- **Key point:** Set expectations for what this talk covers
- **Visual:** Title slide with talk name, presenter, event
- **Notes:** "Today we're going to look at how distributed systems reach agreement—specifically through Raft, an algorithm designed to be understandable."

---

### Slide 2: Distributed systems need agreement
- **Key point:** Without consensus, distributed systems fail in subtle, dangerous ways
- **Visual:** ASCII diagram showing three servers with conflicting state
- **Notes:** "When you have multiple servers, they need to agree—on who's the leader, what operations happened, in what order. Get this wrong and you get split-brain, lost writes, corrupted data."

---

### Slide 3: Raft's core insight is understandability
- **Key point:** Paxos solves consensus but is notoriously hard to implement correctly; Raft trades some elegance for clarity
- **Visual:** Quote or key phrase: "Understandability as a first-class design goal"
- **Notes:** "The Raft paper explicitly says: we optimized for understandability. This matters because a consensus algorithm you can't reason about is one you can't debug when it fails at 3am."

---

## Part 1: The Foundation (4 slides)

### Slide 4: Three roles define every server's behavior
- **Key point:** At any moment, a server is exactly one of: Leader, Candidate, or Follower
- **Visual:** Code block showing Role enum
- **Source:** [CODE: src/raftrole.py:30-33]
- **Notes:** "The entire algorithm flows from this. Leaders make decisions, followers accept them, candidates try to become leaders. Simple state machine."

---

### Slide 5: Terms are logical clocks for distributed time
- **Key point:** Terms provide a total ordering across the cluster—higher term always wins
- **Visual:** Timeline showing term progression across servers
- **Notes:** "Physical clocks don't work in distributed systems—network delays, clock drift. Terms solve this. When you see a higher term, you know that server has more recent authority. This is the mechanism that prevents split-brain."

---

### Slide 6: The log is an ordered sequence of commands
- **Key point:** Every server maintains a log; the goal is to keep them identical
- **Visual:** Code block showing LogEntry dataclass
- **Source:** [CODE: src/raftlog.py:27-31]
- **Notes:** "Each entry has a term and a command. The log is append-only from the perspective of committed entries. The algorithm's job is to get all servers to agree on this sequence."

---

### Slide 7: One leader per term, leader's log is truth
- **Key point:** The fundamental invariant—all safety properties flow from this
- **Visual:** ASCII diagram: Leader with log, arrows pointing to followers
- **Notes:** "This is the one thing. If we maintain this invariant—one leader per term, and that leader's log is the source of truth—everything else follows. Elections ensure one leader. Replication ensures the log spreads."

---

## Part 2: Leader Election (6 slides)

### Slide 8: Elections start when followers time out
- **Key point:** No heartbeat from leader means the leader may be dead—time to elect a new one
- **Visual:** Timeline: heartbeat... heartbeat... silence... timeout!
- **Notes:** "Followers expect regular heartbeats. If they don't hear from the leader, they assume it's dead and start an election. This is distributed failure detection."

---

### Slide 9: Becoming a candidate means incrementing term and voting for yourself
- **Key point:** The candidate increments its term (claiming authority) and casts the first vote
- **Visual:** Code showing state change on timeout
- **Source:** [CODE: src/raftrole.py:147-150]
- **Notes:** "Notice: increment term, vote for self. The term increment is crucial—it establishes a new epoch. Anyone who sees this higher term knows there's a new election happening."

---

### Slide 10: Vote requests carry proof of log completeness
- **Key point:** Candidates must prove their log is at least as complete as the voter's
- **Visual:** Code block showing RequestVoteRequest structure
- **Source:** [CODE: src/raftmessage.py:103-107]
- **Notes:** "The candidate sends its term, plus its last log index and term. This lets voters verify: should I trust this candidate to have all committed entries?"

---

### Slide 11: Vote granting enforces safety constraints
- **Key point:** Voters only grant votes if the candidate's log is at least as up-to-date
- **Visual:** Code block showing vote granting logic
- **Source:** [CODE: src/raftstate.py:427-450]
- **Notes:** "Three checks: term must be current, log must be at least as long, last entry's term must be at least as high. Plus: only one vote per term. This ensures only candidates with complete logs can win."

---

### Slide 12: Majority means authority
- **Key point:** A candidate becomes leader when it receives votes from a majority
- **Visual:** ASCII diagram showing 3 servers, vote flow, majority achieved
- **Notes:** "Why majority? Because any two majorities overlap. If a leader was elected with certain committed entries, any future leader must have gotten a vote from someone who knew about those entries."

---

### Slide 13: Split votes resolve through randomized timeouts
- **Key point:** When no candidate wins, random timeouts ensure someone eventually wins
- **Visual:** Timeline showing two candidates splitting votes, then one winning after random delay
- **Notes:** "What if two candidates start simultaneously and split the vote? Neither gets majority. Solution: randomize election timeouts. Statistically, someone will start first and win."

---

## Part 3: Log Replication (6 slides)

### Slide 14: Client requests go to the leader
- **Key point:** Leaders are the entry point for all writes
- **Visual:** Diagram: Client → Leader → appends to log
- **Notes:** "Clients send commands to the leader. The leader appends to its local log first, then replicates to followers. This is the start of the consensus process."

---

### Slide 15: AppendEntries carries the replication payload
- **Key point:** The message includes everything needed to verify and apply entries
- **Visual:** Code block showing AppendEntryRequest structure
- **Source:** [CODE: src/raftmessage.py:82-88]
- **Notes:** "Term for authority check. Previous index and term for consistency check. Entries to replicate. Commit index so followers know what's safe to apply."

---

### Slide 16: The consistency check prevents gaps and conflicts
- **Key point:** Followers verify that their log matches the leader's before accepting entries
- **Visual:** Code block showing append_entries consistency checks
- **Source:** [CODE: src/raftlog.py:52-58]
- **Notes:** "Two checks: no gaps (previous_index must exist), and terms must match at that position. If either fails, the follower rejects—telling the leader to back up and retry."

---

### Slide 17: On conflict, the leader's log wins
- **Key point:** If logs diverge, the leader's entries overwrite the follower's
- **Visual:** Code block showing conflict resolution
- **Source:** [CODE: src/raftlog.py:63-66]
- **Notes:** "When terms don't match, we delete the conflicting entry and everything after it. Then append the leader's entries. The leader's log is truth—that's the invariant."

---

### Slide 18: Entries are safe once replicated to a majority
- **Key point:** The commit point advances when a majority of servers have an entry
- **Visual:** Code block showing commit index advancement
- **Source:** [CODE: src/raftstate.py:228-241]
- **Notes:** "An entry is committed when it's on a majority of servers. At that point, any future leader must have it. The leader tracks match_index for each follower, advances commit_index when majority is reached."

---

### Slide 19: Committed entries survive failures
- **Key point:** Once committed, an entry will be in every future leader's log
- **Visual:** Diagram showing server failure, new election, committed entries preserved
- **Notes:** "This is the payoff. Committed entries are durable. Even if the leader dies, the election mechanism ensures only candidates with those entries can win. Safety and liveness from the same mechanism."

---

## Closing (3 slides)

### Slide 20: What we didn't cover
- **Key point:** Raft has more features; this was the core algorithm
- **Visual:** Bullet list: membership changes, log compaction/snapshots, read consistency
- **Notes:** "Raft handles more: adding/removing servers, compacting the log, linearizable reads. But the core—elections and replication backed by terms—is what we covered today."

---

### Slide 21: The implementation: 2,400 lines of Python
- **Key point:** This is real, running code—not pseudocode
- **Visual:** Stats: files, lines, test coverage
- **Notes:** "Everything shown today is from a working implementation. The separation between state machine logic and networking makes it possible to test and reason about. Built during David Beazley's Rafting Trip course."

---

### Slide 22: Questions / Resources
- **Key point:** Where to learn more
- **Visual:** Links: Raft paper, visualization, this implementation
- **Notes:** "The Raft paper is readable—that was the point. The raft.github.io visualization is excellent for building intuition. And the code is available if you want to trace through it yourself."

---

## Code Sources Summary

| Slide | Source | Lines | Purpose |
|-------|--------|-------|---------|
| 4 | raftrole.py | 30-33 | Role enum |
| 6 | raftlog.py | 27-31 | LogEntry dataclass |
| 9 | raftrole.py | 147-150 | Timeout → candidate state change |
| 10 | raftmessage.py | 103-107 | RequestVoteRequest structure |
| 11 | raftstate.py | 427-450 | Vote granting logic |
| 15 | raftmessage.py | 82-88 | AppendEntryRequest structure |
| 16 | raftlog.py | 52-58 | Consistency check |
| 17 | raftlog.py | 63-66 | Conflict resolution |
| 18 | raftstate.py | 228-241 | Commit index advancement |

## Narrative Arc Check

Reading the headlines in sequence:

1. Understanding Raft
2. Distributed systems need agreement
3. Raft's core insight is understandability
4. Three roles define every server's behavior
5. Terms are logical clocks for distributed time
6. The log is an ordered sequence of commands
7. One leader per term, leader's log is truth
8. Elections start when followers time out
9. Becoming a candidate means incrementing term and voting for yourself
10. Vote requests carry proof of log completeness
11. Vote granting enforces safety constraints
12. Majority means authority
13. Split votes resolve through randomized timeouts
14. Client requests go to the leader
15. AppendEntries carries the replication payload
16. The consistency check prevents gaps and conflicts
17. On conflict, the leader's log wins
18. Entries are safe once replicated to a majority
19. Committed entries survive failures
20. What we didn't cover
21. The implementation: 2,400 lines of Python
22. Questions / Resources

**Assessment:** The arc builds from problem → core concepts → elections → replication → safety guarantees → wrap-up. Each section escalates complexity appropriately. The One Thing ("leader authority backed by term numbers") appears explicitly in slide 7 and recurs throughout.
