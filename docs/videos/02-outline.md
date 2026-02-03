# Scene Outline: Raft Consensus Overview

**Target duration: 180 seconds (3 minutes)**

---

## Scene 1: Hook — The Problem
**Duration: 15 seconds**

One-line: Three servers need to agree, but messages can fail and servers can crash.

- Show three nodes, one goes dark (crash)
- Question appears: "How do the remaining two agree on what happened?"
- Key visual: Uncertainty without coordination

**Animation needed:** Node failure, question mark appearance

---

## Scene 2: The Three Rules
**Duration: 10 seconds**

One-line: Introduce Raft's three core principles as the answer.

- Text reveals: "Higher terms win. Continuity checks. Majority decides."
- These become the throughline for the rest of the video

**Animation needed:** Text reveal with emphasis

---

## Scene 3: Roles and Terms
**Duration: 25 seconds**

One-line: Every server has a role (Follower/Candidate/Leader) and tracks a term number.

- Show three nodes in Follower state
- Introduce term number (starts at 0)
- Show Leader role appearing — "one leader per term"
- Emphasize: term number is a logical clock

**Animation needed:** Role labels appearing, term counter, leader crown/highlight

---

## Scene 4: Leader Election
**Duration: 45 seconds**

One-line: When followers don't hear from a leader, they become candidates and request votes.

- Follower timeout fires (clock visual)
- Node becomes Candidate, increments term to 1
- Sends RequestVote to other nodes
- Other nodes grant votes (arrows back)
- Candidate becomes Leader with majority
- Key insight: "Higher term always wins — old leaders step down"

**Animation needed:** Timeout clock, role transition, vote arrows, majority counting

---

## Scene 5: Log Replication
**Duration: 50 seconds**

One-line: Leader sends log entries to followers; followers verify continuity before accepting.

- Show leader with log entries [A, B, C]
- Leader sends AppendEntries to followers
- Follower checks: "Does my log match at the boundary?"
- Show successful replication (logs align)
- Show conflict case: follower has different entry
- Leader "walks backward" until finding match point
- Once match found, follower accepts new entries

**Animation needed:** Log stacks, message arrows, continuity check highlight, backtrack animation

---

## Scene 6: Commit and Safety
**Duration: 25 seconds**

One-line: Entry is committed only when majority has replicated it.

- Show leader tracking `match_index` for each follower
- Two followers confirm → majority reached
- Commit index advances
- Key insight: "Once committed, entry is permanent — no rollback"

**Animation needed:** Match index counters, majority threshold line, commit highlight

---

## Scene 7: Putting It Together
**Duration: 10 seconds**

One-line: The three rules work together to guarantee safety.

- Quick visual recap:
  - Terms prevent split-brain (two leaders)
  - Continuity checks prevent log divergence
  - Majority quorum makes consensus real

**Animation needed:** Three rules with checkmarks, nodes in stable state

---

## Timing Budget

| Scene | Duration | Cumulative |
|-------|----------|------------|
| 1. Hook | 15s | 15s |
| 2. Three Rules | 10s | 25s |
| 3. Roles and Terms | 25s | 50s |
| 4. Leader Election | 45s | 95s |
| 5. Log Replication | 50s | 145s |
| 6. Commit and Safety | 25s | 170s |
| 7. Putting It Together | 10s | 180s |

**Total: 180 seconds (3 minutes)** ✓

---

## Animation vs Static

| Scene | Requires Animation | Could Be Static |
|-------|-------------------|-----------------|
| 1. Hook | Node failure, question | - |
| 2. Three Rules | Text reveal | Text could be static |
| 3. Roles and Terms | Role transitions | Node layout |
| 4. Leader Election | Vote flow, majority counting | - |
| 5. Log Replication | Backtrack algorithm | Log structure |
| 6. Commit and Safety | Commit advancing | Match index display |
| 7. Recap | Checkmarks | Summary text |

**Key transformations:**
- Scene 4: Follower → Candidate → Leader (the core state machine)
- Scene 5: Divergent logs → Aligned logs (the consistency mechanism)
- Scene 6: Uncommitted → Committed (the safety property)
