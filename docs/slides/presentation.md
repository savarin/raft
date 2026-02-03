---
marp: true
theme: gaia
paginate: true
---

<!-- _class: lead -->

# Understanding Raft

Distributed Consensus for Humans

**Recurse Center**
February 2026

<!--
Today we're going to look at how distributed systems reach agreement—specifically through Raft, an algorithm designed to be understandable. Everything I show you is from a working implementation.
-->

---

# Distributed systems need agreement

```
Server A:  balance = $100
Server B:  balance = $150  ← which is right?
Server C:  balance = $100
```

Without consensus:
- Split-brain scenarios
- Lost writes
- Corrupted data

<!--
When you have multiple servers, they need to agree—on who's the leader, what operations happened, in what order. Get this wrong and you get split-brain, lost writes, corrupted data. This is the fundamental problem Raft solves.
-->

---

# Raft's core insight is understandability

> "We optimized for understandability"
> — Ongaro & Ousterhout, 2014

Paxos solves consensus but is notoriously hard to implement correctly.

Raft trades some elegance for clarity.

<!--
The Raft paper explicitly says: we optimized for understandability. This matters because a consensus algorithm you can't reason about is one you can't debug when it fails at 3am. Paxos is correct, but Raft is implementable.
-->

---

<!-- _class: invert -->

# Part 1: The Foundation

<!--
Let's establish the core concepts. Everything else builds on these four ideas: roles, terms, logs, and the central invariant.
-->

---

# Three roles define every server's behavior

```python
# from src/raftrole.py:30
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
```

At any moment, a server is exactly one of these.

<!--
The entire algorithm flows from this. Leaders make decisions, followers accept them, candidates try to become leaders. Simple state machine. A server transitions between these roles based on messages and timeouts.
-->

---

# Terms are logical clocks for distributed time

```
Term 1     Term 2     Term 3
  |          |          |
  L1 dies    L2 elected L2 continues
  |          |          |
```

Higher term always wins. This prevents split-brain.

<!--
Physical clocks don't work in distributed systems—network delays, clock drift. Terms solve this. When you see a higher term, you know that server has more recent authority. This is the mechanism that prevents split-brain.
-->

---

# The log is an ordered sequence of commands

```python
# from src/raftlog.py:27
@dataclasses.dataclass
class LogEntry:
    term: int
    item: str
```

Every server maintains a log. The goal: keep them identical.

<!--
Each entry has a term and a command. The log is append-only from the perspective of committed entries. The algorithm's job is to get all servers to agree on this sequence.
-->

---

# One leader per term, leader's log is truth

```
    Leader (term 3)
    [A][B][C][D]
       ↓   ↓
  Follower  Follower
  [A][B]    [A][B][C]
```

**The fundamental invariant.** All safety properties flow from this.

<!--
This is the one thing to remember. If we maintain this invariant—one leader per term, and that leader's log is the source of truth—everything else follows. Elections ensure one leader. Replication ensures the log spreads.
-->

---

<!-- _class: invert -->

# Part 2: Leader Election

<!--
How does a server become leader? Through elections. Let's trace through the process step by step.
-->

---

# Elections start when followers time out

```
Heartbeat ✓  Heartbeat ✓  ...silence...  TIMEOUT!
    |            |            |              |
    └────────────┴────────────┴──────────────┘
                                    ↓
                            Start election
```

No heartbeat from leader → leader may be dead → elect a new one.

<!--
Followers expect regular heartbeats. If they don't hear from the leader, they assume it's dead and start an election. This is distributed failure detection. The timeout is randomized to avoid everyone starting elections simultaneously.
-->

---

# Becoming a candidate: increment term, vote for self

```python
# from src/raftrole.py:147
# timeout triggers state change
case (Role.TIMER, Role.FOLLOWER):
    current_term = target_term + 1    # ← new epoch
    voted_for = Operation.INITIALIZE  # ← vote for self
    role_change = (Role.FOLLOWER, Role.CANDIDATE)
```

<!--
Notice: increment term, vote for self. The term increment is crucial—it establishes a new epoch. Anyone who sees this higher term knows there's a new election happening.
-->

---

# Vote requests carry proof of log completeness

```python
# from src/raftmessage.py:103
@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int      # candidate's term
    last_log_index: int    # how complete is my log?
    last_log_term: int     # how recent is my last entry?
```

Candidates must prove their log is at least as complete as the voter's.

<!--
The candidate sends its term, plus its last log index and term. This lets voters verify: should I trust this candidate to have all committed entries?
-->

---

# Vote granting enforces safety constraints

```python
# from src/raftstate.py:427
# Require candidate have higher term
if current_term < self.current_term:
    success = False

# Require candidate have at least same log length
elif last_log_index < len(self.log) - 1:
    success = False

# Require candidate have last entry with at least same term
elif len(self.log) > 0 and last_log_term < self.log[-1].term:
    success = False
```

Plus: only one vote per term.

<!--
Three checks: term must be current, log must be at least as long, last entry's term must be at least as high. Plus: only one vote per term. This ensures only candidates with complete logs can win.
-->

---

# Majority means authority

```
     Candidate (term 4)
        ↑    ↑
      vote  vote
       /      \
  Follower   Follower

  2 votes + self = 3/3 majority → Leader!
```

Any two majorities overlap → committed entries always survive.

<!--
Why majority? Because any two majorities overlap. If a leader was elected with certain committed entries, any future leader must have gotten a vote from someone who knew about those entries.
-->

---

# Split votes resolve through randomized timeouts

```
Time →
Candidate A: [----timeout----][election]
Candidate B:      [-------timeout-------][election]
                                          ↑
                                    A wins first
```

When no candidate wins, random timeouts ensure eventual success.

<!--
What if two candidates start simultaneously and split the vote? Neither gets majority. Solution: randomize election timeouts. Statistically, someone will start first and win. Simple but effective.
-->

---

<!-- _class: invert -->

# Part 3: Log Replication

<!--
Once we have a leader, how does it spread entries to followers? Through AppendEntries—the workhorse of Raft.
-->

---

# Client requests go to the leader

```
Client → Leader → [append to log] → replicate to followers
```

The leader is the entry point for all writes.

<!--
Clients send commands to the leader. The leader appends to its local log first, then replicates to followers. This is the start of the consensus process.
-->

---

# AppendEntries carries the replication payload

```python
# from src/raftmessage.py:82
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int                   # authority check
    previous_index: int                 # consistency check
    previous_term: int                  # consistency check
    entries: List[raftlog.LogEntry]     # data to replicate
    commit_index: int                   # what's safe to apply
```

<!--
Term for authority check. Previous index and term for consistency check. Entries to replicate. Commit index so followers know what's safe to apply. Everything needed in one message.
-->

---

# The consistency check prevents gaps and conflicts

```python
# from src/raftlog.py:52
# No gaps: previous_index must exist in log
if previous_index >= len(log):
    return False

# Terms must match at previous position
if previous_index >= 0 and log[previous_index].term != previous_term:
    return False
```

If checks fail → follower rejects → leader backs up and retries.

<!--
Two checks: no gaps (previous_index must exist), and terms must match at that position. If either fails, the follower rejects—telling the leader to back up and retry.
-->

---

# On conflict, the leader's log wins

```python
# from src/raftlog.py:63
# If existing entry conflicts with new one (different terms),
# delete existing and everything after
for n, entry in enumerate(entries, start=previous_index + 1):
    if n < len(log) and log[n].term != entry.term:
        del log[n:]   # ← leader's log is truth
        break
```

<!--
When terms don't match, we delete the conflicting entry and everything after it. Then append the leader's entries. The leader's log is truth—that's the invariant.
-->

---

# Entries are safe once replicated to a majority

```python
# from src/raftstate.py:228
non_null_match_index_count, potential_commit_index = self.get_index_metrics()

# Require at least majority
if non_null_match_index_count < self.count_majority():
    return None

# Require entry from leader's current term
if len(self.log) > 0 and self.log[potential_commit_index].term == self.current_term:
    self.commit_index = potential_commit_index  # ← safe!
```

<!--
An entry is committed when it's on a majority of servers. At that point, any future leader must have it. The leader tracks match_index for each follower, advances commit_index when majority is reached.
-->

---

# Committed entries survive failures

```
Before:   Leader [A][B][C]✓    Follower [A][B][C]✓
              ↓ dies
After:    Follower becomes Leader
          Must have [C] to win election (majority overlap)
```

Once committed, an entry will be in every future leader's log.

<!--
This is the payoff. Committed entries are durable. Even if the leader dies, the election mechanism ensures only candidates with those entries can win. Safety and liveness from the same mechanism—terms.
-->

---

# What we didn't cover

- **Membership changes** — adding/removing servers safely
- **Log compaction** — snapshots to bound log size
- **Read consistency** — linearizable reads without writes
- **Performance** — batching, pipelining, persistence

The core algorithm handles elections and replication.

<!--
Raft handles more: adding/removing servers, compacting the log, linearizable reads. But the core—elections and replication backed by terms—is what we covered today. The paper covers the rest.
-->

---

# This implementation: ~1,200 lines of core logic

| File | Purpose | Lines |
|------|---------|-------|
| `raftlog.py` | Log operations | 74 |
| `raftrole.py` | Role transitions | 271 |
| `raftstate.py` | State machine | 648 |
| `raftmessage.py` | Message types | 218 |

Separation of concerns: state machine logic is testable in isolation.

<!--
Everything shown today is from a working implementation. The separation between state machine logic and networking makes it possible to test and reason about. Built during David Beazley's Rafting Trip course.
-->

---

<!-- _class: lead -->

# Questions?

**Resources:**
- [Raft paper](https://raft.github.io/raft.pdf) — readable by design
- [raft.github.io](https://raft.github.io/) — interactive visualization
- This implementation — ask me for the link

<!--
The Raft paper is readable—that was the point. The raft.github.io visualization is excellent for building intuition. And the code is available if you want to trace through it yourself. Questions?
-->
