# Chapter 2: Architecture Overview

## Introduction

This chapter maps Raft's conceptual components to the codebase structure. Understanding the architecture helps you navigate the implementation and see how each module contributes to the whole. The design separates concerns into distinct layers: log operations, role state machines, protocol handlers, message types, and network I/O.

## 2.1 Module Overview

The implementation consists of nine Python files in the `src/` directory:

| Module | Purpose |
|--------|---------|
| `raftlog.py` | Log entries and the `append_entries` operation |
| `raftrole.py` | Role state machine (follower, candidate, leader) |
| `raftstate.py` | Protocol state and message handlers |
| `raftmessage.py` | Message types and serialization |
| `raftnode.py` | Network infrastructure (sockets, threads, queues) |
| `raftserver.py` | Server runtime (combines state, network, timer) |
| `raftclient.py` | Client for sending commands |
| `raftconfig.py` | Cluster configuration (addresses) |
| `rafthelpers.py` | Bencode encoding/decoding |

Plus test files: `test_raftlog.py`, `test_raftstate.py`, `test_rafthelpers.py`, `test_raftmessage.py`.

## 2.2 The Layered Design

The modules form a layered architecture where each layer depends only on layers below it:

```
┌─────────────────────────────────────────────────────────┐
│                    raftserver.py                        │
│              Runtime: timers, event loop                │
├─────────────────────────────────────────────────────────┤
│                     raftnode.py                         │
│           Network: sockets, threads, queues             │
├─────────────────────────────────────────────────────────┤
│                    raftstate.py                         │
│           Protocol: handlers, state management          │
├───────────────────────────┬─────────────────────────────┤
│       raftrole.py         │       raftmessage.py        │
│   Primitives: roles,      │   Primitives: message       │
│   state transitions       │   types, serialization      │
├───────────────────────────┴─────────────────────────────┤
│                     raftlog.py                          │
│              Core: log entries, append                  │
├─────────────────────────────────────────────────────────┤
│                   rafthelpers.py                        │
│               Utilities: Bencode encoding               │
└─────────────────────────────────────────────────────────┘
```

This layering enables:
- Testing protocol logic without network overhead
- Understanding each component in isolation
- Clear dependency direction (no circular imports)

## 2.3 Message-Driven Architecture

Rather than calling methods directly, nodes communicate through typed messages. This design choice has profound implications.

In a direct-call model, a leader replicating entries might look like:

```python
# NOT how this implementation works
for follower in followers:
    result = follower.append_entries(entries)
    if result.success:
        update_match_index(follower)
```

The message-driven model instead looks like:

```python
# How this implementation works
for follower in followers:
    messages.append(AppendEntryRequest(self.id, follower, entries))
return messages

# Later, when response arrives:
def handle_append_entry_response(self, message):
    if message.success:
        self.update_match_index(message.source)
```

The handler receives a message, updates state, and returns response messages. There's no blocking on remote calls. This model:

1. **Enables deterministic testing**: Feed messages in, check messages out. No mocking network calls.

2. **Makes the protocol explicit**: All communication is visible as data. You can log, inspect, and replay message sequences.

3. **Separates concerns**: The protocol layer doesn't know about sockets or threads. The network layer doesn't know about Raft.

## 2.4 State vs. Behavior

The `RaftState` class contains what a node knows:

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

Handler methods define what a node does:

```python
def handle_append_entries_request(self, source, target, ...) -> List[Message]:
    # Update state based on message
    # Return response messages
```

This separation means:
- State is inspectable (just look at the attributes)
- Behavior is testable (call handlers, check results)
- The same state object can be used with or without a network

## 2.5 The Handler Dispatch Pattern

The `handle_message` method is the central dispatch point:

```python
def handle_message(self, message: raftmessage.Message) -> List[raftmessage.Message]:
    match message:
        case raftmessage.ClientLogAppend():
            return self.handle_client_log_append(**vars(message))

        case raftmessage.AppendEntryRequest():
            return self.handle_append_entries_request(**vars(message))

        case raftmessage.AppendEntryResponse():
            return self.handle_append_entries_response(**vars(message))

        case raftmessage.RequestVoteRequest():
            return self.handle_request_vote_request(**vars(message))

        case raftmessage.RequestVoteResponse():
            return self.handle_request_vote_response(**vars(message))

        # ... other cases
```

Python's `match` statement (3.10+) provides exhaustive pattern matching. Each message type has exactly one handler. The `**vars(message)` unpacks the message's attributes as keyword arguments.

## 2.6 Following the Paper

The docstrings throughout this codebase reference specific sections of the Raft paper. For example, from `raftstate.py`:

```python
"""
State section in Figure 2 of Raft paper:

Persistent state on all servers:
currentTerm     latest term server has seen
votedFor        candidateId that received vote in current term
log[]           log entries

Volatile state on all servers:
commitIndex     index of highest log entry known to be committed
lastApplied     index of highest log entry applied to state machine

Volatile state on leaders:
nextIndex[]     for each server, index of next log entry to send
matchIndex[]    for each server, index of highest log entry replicated
"""
```

This traceability lets you read the paper alongside the code. When you see `self.next_index`, you can look up "nextIndex[]" in Figure 2 to understand its purpose.

The test files similarly reference paper figures:

```python
def test_append_entries_paper(logs_by_identifier):
    # Figure 7a
    assert not raftlog.append_entries(
        logs_by_identifier["a"], 9, 6, [raftlog.LogEntry(6, "6")]
    )
```

## 2.7 Configuration

The `raftconfig.py` module defines the cluster topology:

```python
ADDRESS_BY_IDENTIFIER: Dict[int, Tuple[str, int]] = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

This hardcoded configuration keeps the implementation simple. A production system would support dynamic membership changes, but that's a significant additional complexity (covered in Section 6 of the Raft paper, not implemented here).

## Conclusion

The codebase separates Raft into layers: log operations at the bottom, role and message primitives above that, protocol handlers managing state, and network/runtime at the top. The message-driven architecture enables deterministic testing and clear protocol boundaries. The `handle_message` dispatch routes each message type to its handler. Paper references throughout the code connect implementation to specification. This architecture makes the algorithm visible in the code structure.
