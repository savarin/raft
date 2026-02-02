# Chapter 6: State Attributes and Transitions

## Introduction

This chapter covers the state that nodes maintain and how it changes on role transitions. The `RaftState` class in `raftstate.py` combines the log with role-specific attributes like `nextIndex`, `matchIndex`, and `votedFor`. When a node changes role, some state must be initialized and other state reset. The `Operation` enum and `evaluate_operations` function codify these rules.

## 6.1 The RaftState Class

`RaftState` holds everything a Raft node needs to know:

```python
@dataclasses.dataclass
class RaftState:
    identifier: int

    def __post_init__(self) -> None:
        self.log: List[raftlog.LogEntry] = []
        self.role: raftrole.Role = raftrole.Role.FOLLOWER
        self.current_term: int = -1
        self.next_index: Optional[Dict[int, int]] = None
        self.match_index: Optional[Dict[int, Optional[int]]] = None
        self.commit_index: int = -1
        self.has_followers: Optional[bool] = None
        self.voted_for: Optional[int] = None
        self.current_votes: Optional[Dict[int, Optional[int]]] = None
        self.config: Dict[int, Tuple[str, int]] = raftconfig.ADDRESS_BY_IDENTIFIER
        self.experimental_mode: bool = False
```

Let's examine each attribute:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `identifier` | `int` | This node's unique ID |
| `log` | `List[LogEntry]` | The replicated log |
| `role` | `Role` | Current role (follower/candidate/leader) |
| `current_term` | `int` | Current term number |
| `next_index` | `Dict[int, int]` | (Leader only) Next index to send to each follower |
| `match_index` | `Dict[int, int]` | (Leader only) Highest replicated index per follower |
| `commit_index` | `int` | Highest committed log index |
| `has_followers` | `bool` | (Leader only) Received response since last heartbeat? |
| `voted_for` | `int` | Who this node voted for in current term |
| `current_votes` | `Dict[int, int]` | (Candidate only) Vote tracking |
| `config` | `Dict` | Cluster membership |

## 6.2 Persistent vs. Volatile State

The Raft paper's Figure 2 distinguishes:

**Persistent state (survives restarts):**
- `currentTerm`: Latest term seen
- `votedFor`: Candidate voted for in current term
- `log[]`: Log entries

**Volatile state on all servers:**
- `commitIndex`: Highest committed index
- `lastApplied`: Highest applied index (not tracked in this implementation)

**Volatile state on leaders:**
- `nextIndex[]`: Next index to send per follower
- `matchIndex[]`: Highest replicated index per follower

This implementation keeps everything in memory—there's no persistence. But the distinction still matters: "volatile on leaders" means these attributes only exist when the node is a leader. When it steps down, they're cleared.

## 6.3 Leader-Specific State

When a node becomes leader, it initializes:

**`next_index`**: For each follower, the next log entry to send. Initialized to the leader's log length (optimistically assuming followers are caught up).

```python
self.next_index = {
    identifier: len(self.log) for identifier in self.config
}
```

**`match_index`**: For each follower, the highest index known to be replicated. Initialized to `None` (nothing confirmed yet), except for the leader itself.

```python
self.match_index = {identifier: None for identifier in self.config}
self.match_index[self.identifier] = len(self.log) - 1
```

**`has_followers`**: Tracks whether the leader received any response since the last heartbeat. Used to detect isolation.

```python
self.has_followers = False
```

When a leader steps down, all of these reset to `None`:

```python
self.next_index = None
self.match_index = None
self.has_followers = None
```

## 6.4 Candidate-Specific State

When a node becomes candidate, it initializes:

**`voted_for`**: Set to self (candidates vote for themselves).

```python
self.voted_for = self.identifier
```

**`current_votes`**: Tracks votes received. Initialized with self-vote.

```python
self.current_votes = {identifier: None for identifier in self.config}
self.current_votes[self.identifier] = self.identifier
```

When a candidate becomes follower (lost election or saw higher term), `current_votes` resets:

```python
self.current_votes = None
```

Note that `voted_for` is handled differently—it resets when the term changes, not when the role changes.

## 6.5 The Operation Enum

State changes are expressed through three operations:

```python
class Operation(enum.Enum):
    PASS = "PASS"               # No change to this attribute
    RESET_TO_NONE = "RESET_TO_NONE"  # Clear/reset the attribute
    INITIALIZE = "INITIALIZE"        # Set up for new role
```

This allows `evaluate_operations` to return a complete specification of what should happen to each attribute:

```python
def evaluate_operations(
    role_change: Optional[Tuple[Role, Role]]
) -> Tuple[Operation, Operation, Operation, Operation, Operation]:
```

For example, when becoming leader:

```python
case (Role.CANDIDATE, Role.LEADER):
    next_index = Operation.INITIALIZE
    match_index = Operation.INITIALIZE
    commit_index = Operation.PASS
    has_followers = Operation.INITIALIZE
    current_votes = Operation.PASS  # Keep vote record
```

When stepping down from leader:

```python
case (Role.LEADER, Role.FOLLOWER):
    next_index = Operation.RESET_TO_NONE
    match_index = Operation.RESET_TO_NONE
    commit_index = Operation.RESET_TO_NONE
    has_followers = Operation.RESET_TO_NONE
    current_votes = Operation.RESET_TO_NONE
```

## 6.6 The StateChange TypedDict

The complete state change specification is captured in a TypedDict:

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

The `enumerate_state_change` function produces this specification:

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
        match_index=match_index,
        commit_index=commit_index,
        has_followers=has_followers,
        voted_for=voted_for,
        current_votes=current_votes,
    )
```

## 6.7 Implementing State Changes

The `implement_state_change` method in `RaftState` applies a `StateChange`:

```python
def implement_state_change(self, state_change: raftrole.StateChange) -> None:
    if state_change["role_change"] is not None:
        assert state_change["role_change"][0] == self.role
        self.role = state_change["role_change"][1]

    self.current_term = state_change["current_term"]

    match state_change["next_index"]:
        case raftrole.Operation.RESET_TO_NONE:
            self.next_index = None
        case raftrole.Operation.INITIALIZE:
            self.next_index = {
                identifier: len(self.log) for identifier in self.config
            }

    match state_change["match_index"]:
        case raftrole.Operation.RESET_TO_NONE:
            self.match_index = None
        case raftrole.Operation.INITIALIZE:
            self.match_index = {identifier: None for identifier in self.config}
            self.match_index[self.identifier] = len(self.log) - 1

    # ... similar for other attributes
```

Key observations:

1. The role change is validated: `assert state_change["role_change"][0] == self.role`
2. `PASS` operations are implicit (no case needed)
3. Each attribute's initialization logic is centralized here

## 6.8 Why This Design?

Separating "what changes" (StateChange) from "how to change" (implement_state_change) provides:

**Single source of truth**: All initialization logic is in one place. You don't have scattered `self.next_index = {...}` throughout the codebase.

**Testability**: You can verify state changes without invoking handlers. Just call `enumerate_state_change` and check the result.

**Documentation**: The StateChange TypedDict explicitly lists every attribute that might change. Nothing is implicit.

**Safety**: Pattern matching ensures all cases are handled. Adding a new attribute to StateChange forces you to handle it in `implement_state_change`.

## Conclusion

`RaftState` maintains all per-node state: the log, current role, term, and role-specific attributes. Leader state (`next_index`, `match_index`, `has_followers`) is initialized on election and cleared on step-down. Candidate state (`current_votes`) is initialized on timeout and cleared on becoming follower. The `StateChange` TypedDict and `Operation` enum make these transitions explicit, ensuring that role changes are complete and consistent.
