# Chapter 5: The Role State Machine

## Introduction

This chapter covers how nodes transition between the three roles: follower, candidate, and leader. The `raftrole.py` module codifies these transitions as an explicit state machine. Understanding when and why role changes occur is fundamental to understanding Raft's leader election mechanism.

## Sections

### 5.1 The Three Roles

What each role does:
- **Follower**: Passive. Accepts log entries from leader, grants votes to candidates.
- **Candidate**: Seeking election. Solicits votes, may become leader or revert to follower.
- **Leader**: Active. Sends heartbeats, replicates log entries, responds to clients.

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
```

### 5.2 Auxiliary Roles

The implementation adds three pseudo-roles for triggering state changes:
- `TIMER`: Represents timeout events
- `ELECTION_COMMISSION`: Represents winning an election
- `CONSTITUTION`: Represents leadership rules (step-down on isolation)

These aren't real node states but message sources that trigger transitions.

### 5.3 Term Numbers

Terms are Raft's logical clock. Every message carries the sender's term. If a node sees a higher term, it updates and becomes a follower. This prevents stale leaders.

### 5.4 The evaluate_role_change Function

How `evaluate_role_change` determines whether a role change occurs based on source role, source term, target role, and target term. The exhaustive case matching.

### 5.5 Valid Transitions

The four valid role transitions:
1. Follower → Candidate (timeout, no heartbeat received)
2. Candidate → Leader (wins election)
3. Candidate → Follower (sees higher term or leader's message)
4. Leader → Follower (sees higher term or loses connectivity)

### 5.6 The Rules from Figure 2

How the implementation maps to the "Rules for Servers" section in the paper. Term update rule, follower timeout rule, candidate election rules.

## Conclusion

Nodes cycle through three roles: follower (passive), candidate (seeking votes), and leader (coordinating replication). Role transitions are triggered by timeouts, election results, or messages with higher terms. The `raftrole.py` module encodes these transitions explicitly, making the state machine visible and testable.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Follower, Candidate, Leader roles
- Auxiliary roles (TIMER, ELECTION_COMMISSION, CONSTITUTION)
- Term numbers as logical clocks
- `evaluate_role_change` function
- Valid state transitions

**Back-references**:
- Chapter 1 introduced leader-based replication and terms conceptually
- Chapter 2 identified `raftrole.py` as the role primitive layer

**Forward dependencies**:
- Chapter 6 uses role changes to manage state attributes
- Chapter 8 implements the follower→candidate→leader path
- Chapter 11 uses TIMER role for timeout handling
