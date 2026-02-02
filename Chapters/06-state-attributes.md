# Chapter 6: State Attributes and Transitions

## Introduction

This chapter covers the state that nodes maintain and how it changes on role transitions. The `RaftState` class in `raftstate.py` combines the log with role-specific attributes like `nextIndex`, `matchIndex`, and `votedFor`. When a node changes role, some state must be initialized and other state reset. The `Operation` enum and `evaluate_operations` function codify these rules.

## Sections

### 6.1 The RaftState Class

Overview of `RaftState` attributes:

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
        # ...
```

### 6.2 Persistent vs. Volatile State

From the paper's Figure 2:
- **Persistent**: `currentTerm`, `votedFor`, `log[]` (survive restarts)
- **Volatile on all servers**: `commitIndex`, `lastApplied`
- **Volatile on leaders**: `nextIndex[]`, `matchIndex[]`

This implementation keeps everything in memory (no persistence), but the distinction matters for understanding which state is role-specific.

### 6.3 Leader-Specific State

`nextIndex` and `matchIndex` only exist when a node is leader:
- `nextIndex[i]`: Next log index to send to follower i
- `matchIndex[i]`: Highest log index known replicated on follower i

These are initialized when becoming leader, reset to `None` when stepping down.

### 6.4 Candidate-Specific State

`votedFor` and `currentVotes`:
- `votedFor`: Who this node voted for in the current term
- `currentVotes`: Tracking received votes during an election

### 6.5 The Operation Enum

Three operations for state attributes:
```python
class Operation(enum.Enum):
    PASS = "PASS"           # No change
    RESET_TO_NONE = "RESET_TO_NONE"  # Clear the attribute
    INITIALIZE = "INITIALIZE"        # Set up for new role
```

### 6.6 The StateChange TypedDict

How `enumerate_state_change` returns a complete specification of what changes:

```python
class StateChange(TypedDict):
    role_change: Optional[Tuple[Role, Role]]
    current_term: int
    next_index: Operation
    match_index: Operation
    # ...
```

### 6.7 Implementing State Changes

Walking through `implement_state_change` in `RaftState`. Pattern matching on operations to initialize, reset, or preserve each attribute.

## Conclusion

`RaftState` maintains all per-node state: the log, current role, term, and role-specific attributes. When roles change, some attributes must be initialized (leader's tracking dictionaries) and others reset (candidate's vote tracking). The `StateChange` dictionary and `Operation` enum make these transitions explicit and systematic.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- `RaftState` class and all attributes
- Persistent vs. volatile state distinction
- `nextIndex` and `matchIndex` (leader-specific)
- `votedFor` and `currentVotes` (candidate-specific)
- `Operation` enum (PASS, RESET_TO_NONE, INITIALIZE)
- `StateChange` TypedDict
- `implement_state_change` method

**Back-references**:
- Chapter 3 introduced the log that `RaftState` contains
- Chapter 5 introduced role transitions that trigger state changes

**Forward dependencies**:
- Chapter 8 uses `currentVotes` and `votedFor` for elections
- Chapter 9 uses `nextIndex` and `matchIndex` for replication
