# Chapter 5: The Role State Machine

## Introduction

This chapter covers how nodes transition between the three roles: follower, candidate, and leader. The `raftrole.py` module codifies these transitions as an explicit state machine. Understanding when and why role changes occur is fundamental to understanding Raft's leader election mechanism.

## 5.1 The Three Roles

A Raft node is always in exactly one of three roles:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
```

**Follower**: The passive role. Followers respond to requests from leaders and candidates. They don't initiate communication—they wait for heartbeats from the leader and vote requests from candidates. If a follower doesn't hear from a leader within the election timeout, it becomes a candidate.

**Candidate**: The transitional role. A candidate is seeking to become leader. It increments its term, votes for itself, and asks other nodes for votes. If it receives a majority, it becomes leader. If it sees a message with a higher term (or from a current leader), it reverts to follower.

**Leader**: The active role. The leader handles all client requests, appending commands to its log and replicating them to followers. It sends periodic heartbeats to maintain authority. If it sees a message with a higher term, it steps down to follower.

```
                     timeout
              ┌─────────────────┐
              │                 │
              ▼                 │
         ┌─────────┐       ┌─────────┐
         │FOLLOWER │──────►│CANDIDATE│◄──┐
         └─────────┘       └─────────┘   │
              ▲                 │        │ timeout/
              │                 │        │ split vote
              │    wins         │        │
              │   election      ▼        │
              │            ┌─────────┐   │
              └────────────│ LEADER  │───┘
               sees higher └─────────┘
                   term
```

## 5.2 Auxiliary Roles

The implementation adds three pseudo-roles that represent event sources rather than actual node states:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
    TIMER = "TIMER"
    ELECTION_COMMISSION = "ELECTION_COMMISSION"
    CONSTITUTION = "CONSTITUTION"
```

**TIMER**: Represents timeout events. When a follower's election timeout expires, it's as if a "timer" sent a message causing the transition to candidate.

**ELECTION_COMMISSION**: Represents winning an election. When a candidate receives a majority of votes, the "election commission" triggers its transition to leader.

**CONSTITUTION**: Represents constitutional rules about leadership. If a leader becomes isolated (no follower responses), the "constitution" forces it to step down.

These pseudo-roles simplify the state transition logic by letting all transitions be expressed as "source role + term triggers change in target role."

## 5.3 Term Numbers

Terms are Raft's logical clock. The `current_term` attribute tracks what term a node believes it's in.

```python
self.current_term: int = -1
```

Every message in Raft carries the sender's term. When a node receives a message:

1. If the message's term is greater than the node's current term, update `current_term` and become a follower
2. If the message's term equals the node's term and the sender is a leader (via `AppendEntryRequest`), a candidate becomes a follower
3. If the message's term is less than the node's term, the message is stale (handle accordingly)

This rule ensures that stale leaders can't disrupt the cluster. A leader that was partitioned will have an old term; when it reconnects, it discovers the higher term and steps down.

## 5.4 The evaluate_role_change Function

The `evaluate_role_change` function determines what happens when a node receives a message or event:

```python
def evaluate_role_change(
    source_role: Role, source_term: int, target_role: Role, target_term: int
) -> Tuple[Optional[Tuple[Role, Role]], int, Operation]:
```

It returns:
- A role change tuple (if any): `(from_role, to_role)` or `None`
- The new `current_term`
- An operation for `voted_for`

The function uses exhaustive pattern matching to handle every combination:

```python
match (source_role, target_role):
    # Leader sending to follower
    case (Role.LEADER, Role.FOLLOWER):
        if source_term > target_term:
            current_term = source_term
            voted_for = Operation.RESET_TO_NONE
            role_change = None

    # Leader sending to candidate (candidate sees leader)
    case (Role.LEADER, Role.CANDIDATE):
        if source_term > target_term:
            current_term = source_term
            voted_for = Operation.RESET_TO_NONE
            role_change = (Role.CANDIDATE, Role.FOLLOWER)
        elif source_term == target_term:
            # Same term: leader exists, candidate steps down
            current_term = source_term
            voted_for = Operation.PASS
            role_change = (Role.CANDIDATE, Role.FOLLOWER)

    # Timer triggering follower to become candidate
    case (Role.TIMER, Role.FOLLOWER):
        current_term = target_term + 1
        voted_for = Operation.INITIALIZE  # Vote for self
        role_change = (Role.FOLLOWER, Role.CANDIDATE)

    # ... many more cases
```

## 5.5 Valid Transitions

There are four valid role transitions:

**1. Follower → Candidate** (election timeout)
```python
case (Role.TIMER, Role.FOLLOWER):
    current_term = target_term + 1
    voted_for = Operation.INITIALIZE
    role_change = (Role.FOLLOWER, Role.CANDIDATE)
```
When a follower times out without hearing from a leader, it increments its term, votes for itself, and becomes a candidate.

**2. Candidate → Leader** (wins election)
```python
case (Role.ELECTION_COMMISSION, Role.CANDIDATE):
    current_term = target_term
    voted_for = Operation.PASS
    role_change = (Role.CANDIDATE, Role.LEADER)
```
When a candidate receives a majority of votes, it becomes leader. The term doesn't change (it was already incremented when becoming candidate).

**3. Candidate → Follower** (sees higher term or current leader)
```python
case (Role.LEADER, Role.CANDIDATE):
    if source_term >= target_term:
        role_change = (Role.CANDIDATE, Role.FOLLOWER)
```
If a candidate sees an `AppendEntryRequest` from a leader with an equal or higher term, it steps down. The election is over.

**4. Leader → Follower** (sees higher term or loses connectivity)
```python
case (Role.FOLLOWER, Role.LEADER):
    if source_term > target_term:
        role_change = (Role.LEADER, Role.FOLLOWER)

case (Role.CONSTITUTION, Role.LEADER):
    role_change = (Role.LEADER, Role.FOLLOWER)
```
A leader steps down if it sees a higher term, or if it becomes isolated (no successful heartbeat responses).

## 5.6 The Rules from Figure 2

The paper's Figure 2 specifies "Rules for Servers." Here's how this implementation maps to those rules:

**All Servers:**
> If RPC request or response contains term T > currentTerm: set currentTerm = T, convert to follower

```python
if source_term > target_term:
    current_term = source_term
    voted_for = Operation.RESET_TO_NONE
    role_change = (current_role, Role.FOLLOWER)  # if not already follower
```

**Followers:**
> If election timeout elapses without receiving AppendEntries RPC from current leader or granting vote to candidate: convert to candidate

```python
case (Role.TIMER, Role.FOLLOWER):
    role_change = (Role.FOLLOWER, Role.CANDIDATE)
```

**Candidates:**
> On conversion to candidate, start election: Increment currentTerm, Vote for self

```python
current_term = target_term + 1
voted_for = Operation.INITIALIZE  # sets voted_for = self.identifier
```

> If votes received from majority of servers: become leader

```python
case (Role.ELECTION_COMMISSION, Role.CANDIDATE):
    role_change = (Role.CANDIDATE, Role.LEADER)
```

> If AppendEntries RPC received from new leader: convert to follower

```python
case (Role.LEADER, Role.CANDIDATE):
    if source_term == target_term:
        role_change = (Role.CANDIDATE, Role.FOLLOWER)
```

## 5.7 Why Explicit State Machines?

Making the state machine explicit has several benefits:

**Testability**: You can enumerate all possible transitions and verify each one behaves correctly.

**Documentation**: The code itself documents the valid transitions. No hidden paths.

**Safety**: The exhaustive match forces you to handle every case. Missing a transition causes a compile/runtime error.

Compare this to implicit state management where role changes are scattered across handlers. That approach makes it hard to verify all transitions are correct and complete.

## Conclusion

Nodes cycle through three roles: follower (passive), candidate (seeking votes), and leader (coordinating replication). Role transitions are triggered by timeouts, election results, or messages with higher terms. The `raftrole.py` module encodes these transitions explicitly through `evaluate_role_change`, making the state machine visible, testable, and traceable to the paper's specification.
