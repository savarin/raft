# Chapter 4: Roles and State Transitions

A Raft server is always in one of three roles: Follower, Candidate, or Leader. This chapter explains what each role does, when servers transition between roles, and how the implementation encodes these rules.

Roles are simpler than they might appear. Followers wait. Candidates seek votes. Leaders replicate logs. The complexity is in the transitions—knowing when to change roles and what state to reset when you do.

## The Three Roles

### Follower

Follower is the default state. Every server starts as a follower and returns to being a follower when things go wrong.

Followers are passive. They:

- Accept log entries from the leader via AppendEntries RPCs
- Grant votes to candidates via RequestVote RPCs
- Wait for heartbeats from the leader

If a follower doesn't hear from a leader within its timeout period, something is wrong. Maybe the leader crashed. Maybe the network partitioned. Either way, the follower transitions to candidate and tries to become the new leader.

### Candidate

Candidate is a transitional state. Servers become candidates to try to become leaders; they never stay candidates for long.

When a server becomes a candidate, it:

1. Increments its term (starting a new election period)
2. Votes for itself
3. Sends RequestVote RPCs to all other servers
4. Waits for responses

Three things can happen:

- **Win**: The candidate receives votes from a majority. It becomes leader.
- **Lose**: The candidate receives an AppendEntries from another server claiming to be leader with an equal or higher term. It becomes follower.
- **Timeout**: Neither of the above happens within the timeout period. The candidate increments term and starts another election.

The timeout case handles split votes—when multiple candidates split the votes so nobody gets a majority. Random timeout values make it unlikely that the same candidates tie repeatedly.

### Leader

Leader is the active state. At most one leader exists per term.

Leaders:

- Send periodic heartbeats (empty AppendEntries) to maintain authority
- Accept client commands and add them to the log
- Replicate log entries to followers
- Track which entries are committed (replicated to a majority)

A leader continues until it discovers a higher term (from any RPC) or fails to communicate with followers. In this implementation, if a leader sends heartbeats but receives no responses, it steps down. This handles the case where a leader is partitioned from the rest of the cluster.

## Terms

Terms are Raft's logical clock. Every message carries a term number. Every server tracks its current term.

Key properties:

- Terms increase monotonically. They never decrease.
- Each term has at most one leader. (It might have zero if no candidate wins the election.)
- If a server receives a message with a higher term, it updates its term and converts to follower.

The last property is crucial. It means stale leaders can't cause trouble. If an old leader comes back online after a partition heals, it will see the higher term and step down before doing anything harmful.

## The Role Enum

The implementation defines roles as an enum:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
    TIMER = "TIMER"
    ELECTION_COMMISSION = "ELECTION_COMMISSION"
    CONSTITUTION = "CONSTITUTION"
```

Wait—six values for three roles? The additional values are pseudo-roles that represent internal events:

- **TIMER**: Represents a timeout event. When a follower times out, it's as if a message arrived from "TIMER" triggering the transition to candidate.
- **ELECTION_COMMISSION**: Represents winning an election. When a candidate gets majority votes, it's as if "ELECTION_COMMISSION" announced the victory.
- **CONSTITUTION**: Represents losing leadership. When a leader fails to communicate with followers, "CONSTITUTION" tells it to step down.

These pseudo-roles let the state transition logic handle all cases uniformly. Instead of special-casing timeouts, the code treats them as messages from these internal sources.

## The State Change Rules

Figure 2 of the Raft paper specifies the rules:

> **All Servers**: If RPC request or response contains term T > currentTerm: set currentTerm = T, convert to follower

> **Followers**: If election timeout elapses without receiving AppendEntries RPC from current leader or granting vote to candidate: convert to candidate

> **Candidates**: On conversion to candidate, start election: Increment currentTerm, Vote for self, Reset election timer, Send RequestVote RPCs to all other servers

The `evaluate_role_change` function encodes these rules as a pattern match on (source_role, target_role):

```python
def evaluate_role_change(
    source_role: Role, source_term: int, target_role: Role, target_term: int
) -> Tuple[Optional[Tuple[Role, Role]], int, Operation]:

    match (source_role, target_role):
        # If receiving AppendEntry from leader with higher term
        case (Role.LEADER, Role.FOLLOWER):
            if source_term > target_term:
                current_term = source_term
                voted_for = Operation.RESET_TO_NONE
                role_change = None  # Already follower

        # If receiving AppendEntry as candidate
        case (Role.LEADER, Role.CANDIDATE):
            if source_term > target_term:
                current_term = source_term
                voted_for = Operation.RESET_TO_NONE
                role_change = (Role.CANDIDATE, Role.FOLLOWER)
            elif source_term == target_term:
                # Same term: leader exists, step down
                role_change = (Role.CANDIDATE, Role.FOLLOWER)

        # Timeout: follower becomes candidate
        case (Role.TIMER, Role.FOLLOWER):
            current_term = target_term + 1
            voted_for = Operation.INITIALIZE  # Vote for self
            role_change = (Role.FOLLOWER, Role.CANDIDATE)

        # Win election: candidate becomes leader
        case (Role.ELECTION_COMMISSION, Role.CANDIDATE):
            role_change = (Role.CANDIDATE, Role.LEADER)

        # No heartbeat responses: leader steps down
        case (Role.CONSTITUTION, Role.LEADER):
            role_change = (Role.LEADER, Role.FOLLOWER)
```

The function returns three things: whether the role changes (and to what), what the new term should be, and whether `voted_for` should be reset.

## State Attributes and Operations

Role transitions affect more than just the role. When a server becomes leader, it needs to initialize `nextIndex` and `matchIndex`. When it stops being leader, those should reset to None.

The `Operation` enum describes what to do with each attribute:

```python
class Operation(enum.Enum):
    PASS = "PASS"           # Leave unchanged
    RESET_TO_NONE = "RESET_TO_NONE"  # Set to None
    INITIALIZE = "INITIALIZE"  # Set up initial values
```

The `evaluate_operations` function determines the operation for each attribute based on the role change:

```python
def evaluate_operations(
    role_change: Optional[Tuple[Role, Role]]
) -> Tuple[Operation, Operation, Operation, Operation, Operation]:

    match role_change:
        case (Role.FOLLOWER, Role.CANDIDATE):
            # Initialize vote tracking
            current_votes = Operation.INITIALIZE

        case (Role.CANDIDATE, Role.LEADER):
            # Initialize leader tracking structures
            next_index = Operation.INITIALIZE
            match_index = Operation.INITIALIZE
            has_followers = Operation.INITIALIZE

        case (Role.LEADER, Role.FOLLOWER):
            # Clear everything
            next_index = Operation.RESET_TO_NONE
            match_index = Operation.RESET_TO_NONE
            commit_index = Operation.RESET_TO_NONE
            has_followers = Operation.RESET_TO_NONE
            current_votes = Operation.RESET_TO_NONE
```

Note that when a leader steps down, `commit_index` resets. This is safe but potentially wasteful—the follower will receive the correct commit index from the new leader's heartbeats.

## The StateChange TypedDict

The complete state change is captured in a typed dictionary:

```python
class StateChange(TypedDict):
    role_change: Optional[Tuple[Role, Role]]
    current_term: int
    next_index: Operation
    match_index: Operation
    commit_index: Operation
    has_followers: Operation
    voted_for: Operation
    current_votes: Operation
```

The `enumerate_state_change` function computes this dictionary from the source and target roles and terms:

```python
def enumerate_state_change(
    source_role: Role,
    source_term: int,
    target_role: Role,
    target_term: int,
) -> StateChange:
    role_change, current_term, voted_for = evaluate_role_change(
        source_role, source_term, target_role, target_term
    )

    (
        next_index,
        match_index,
        commit_index,
        has_followers,
        current_votes,
    ) = evaluate_operations(role_change)

    return dict(
        role_change=role_change,
        current_term=current_term,
        next_index=next_index,
        # ...
    )
```

This separation—computing what should change separately from actually changing it—keeps the logic testable. You can call `enumerate_state_change` with any inputs and verify the output without modifying any state.

## The State Machine Diagram

The transitions between roles form a simple state machine:

```
                    timeout
         +---------------------------+
         |                           |
         v                           |
    +---------+    timeout      +-----------+
    | FOLLOWER| --------------> | CANDIDATE |
    +---------+                 +-----------+
         ^                           |
         |    higher term            | majority votes
         |    or leader exists       |
         |                           v
         |                      +---------+
         +----------------------|  LEADER |
              no responses      +---------+
              or higher term
```

Followers become candidates on timeout. Candidates become leaders on winning. Leaders become followers on losing contact or seeing a higher term. Any role can become follower on seeing a higher term.

## Why This Design

The role and transition logic is pure functions in a separate module (`raftrole.py`). This has several benefits:

1. **Testability**: You can test transition logic without creating actual servers or sending messages.

2. **Clarity**: The rules are explicit, enumerated in code. No hidden state machines buried in handlers.

3. **Single responsibility**: `raftstate.py` handles messages; `raftrole.py` handles transitions.

The pseudo-roles (TIMER, ELECTION_COMMISSION, CONSTITUTION) might seem like overkill, but they let the same pattern-matching logic handle both external RPCs and internal events. The alternative would be special cases scattered throughout the code.

## Conclusion

Three roles, four transitions, and a set of attributes that reset on each transition. The `raftrole` module encodes these rules as pure functions—given the current state and an event, compute the new state.

The state machine (Chapter 5) uses these functions to implement the actual transitions. When `RaftState` processes a message, it calls `enumerate_state_change` to determine what should happen, then applies the result. That's next.
