---
marp: true
theme: default
paginate: true
backgroundColor: #1a1a2e
color: #eaeaea
style: |
  h1, h2, h3 {
    color: #00d4ff;
  }
  code {
    background-color: #16213e;
  }
  pre {
    background-color: #16213e;
  }
---

# Codebase Architecture

## Module Overview

---

# Project Structure

```
src/
├── raftstate.py      # Core state machine (648 lines)
├── raftrole.py       # Role management (271 lines)
├── raftmessage.py    # Message types (218 lines)
├── raftnode.py       # Network layer (156 lines)
├── raftserver.py     # Server entry point (103 lines)
├── raftlog.py        # Log management (74 lines)
├── raftclient.py     # Client interface (65 lines)
├── raftconfig.py     # Configuration (8 lines)
└── rafthelpers.py    # Bencode utilities (68 lines)
```

---

# Module Dependencies

```
                    +--------------+
                    | raftserver   |  Entry Point
                    +--------------+
                          |
           +--------------+--------------+
           |              |              |
           v              v              v
    +-----------+  +-----------+  +-----------+
    | raftstate |  | raftnode  |  |  Timer    |
    +-----------+  +-----------+  +-----------+
           |              |
           v              v
    +-----------+  +-----------+
    | raftrole  |  | raftconfig|
    | raftlog   |  +-----------+
    | raftmsg   |
    +-----------+
```

---

# raftstate.py — The Heart

The core state machine implementing Raft logic

**State Variables:**
```python
current_term: int       # Current term number
voted_for: int | None   # Who we voted for this term
log: list[LogEntry]     # Replicated log
commit_index: int       # Highest committed index
last_applied: int       # Highest applied index
role: Role              # FOLLOWER, CANDIDATE, or LEADER
```

**Leader-only state:**
```python
next_index: dict[int, int]   # Next entry to send to each
match_index: dict[int, int]  # Confirmed replication progress
```

---

# raftstate.py — Message Handling

Uses Python 3.10+ pattern matching

```python
def handle_message(self, message: Message) -> list[Message]:
    match message:
        case ClientLogAppend():
            return self.handle_client_log_append(...)
        case AppendEntryRequest():
            return self.handle_append_entries_request(...)
        case RequestVoteRequest():
            return self.handle_request_vote_request(...)
        case AppendEntryResponse():
            return self.handle_append_entries_response(...)
        # ... etc
```

---

# raftrole.py — State Transitions

Defines roles and transition rules from the Raft paper

```python
class Role(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"
```

**Pseudo-roles for state changes:**
```python
class PseudoRole(Enum):
    TIMER = "TIMER"              # Timeout events
    ELECTION_COMMISSION = "EC"   # Vote counting
    CONSTITUTION = "CONST"       # Higher term discovery
```

---

# raftmessage.py — Message Types

Nine message types as dataclasses:

```python
@dataclass
class ClientLogAppend:      # Client → Leader
@dataclass
class UpdateFollowers:      # Internal heartbeat trigger
@dataclass
class AppendEntryRequest:   # Leader → Follower
@dataclass
class AppendEntryResponse:  # Follower → Leader
@dataclass
class RunElection:          # Internal election trigger
@dataclass
class RequestVoteRequest:   # Candidate → All
@dataclass
class RequestVoteResponse:  # Server → Candidate
@dataclass
class RoleChange:           # Internal role transition
```

---

# raftnode.py — Network Layer

TCP socket-based communication

```python
ADDRESS_BY_IDENTIFIER = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

**Threading model:**
- Background listener thread (accepts connections)
- Background deliverer thread (sends outgoing messages)
- Queue-based message passing

---

# raftlog.py — Log Management

Implements the append_entries algorithm

```python
@dataclass
class LogEntry:
    term: int    # Term when entry received
    item: str    # Command payload

def append_entries(
    log: list[LogEntry],
    prev_log_index: int,
    prev_log_term: int,
    entries: list[LogEntry],
) -> tuple[bool, list[LogEntry]]:
    # Returns (success, updated_log)
```

---

# raftserver.py — Orchestration

Brings everything together

```python
class RaftServer:
    def __init__(self, identifier: int):
        self.state = RaftState(identifier)
        self.node = RaftNode(identifier)
        self.timer = None

    def run(self):
        while True:
            message = self.node.receive()
            responses = self.state.handle_message(message)
            for response in responses:
                self.node.send(response)
            self.cycle()  # Reset timer
```

---

# rafthelpers.py — Serialization

Bencode format (used in BitTorrent)

```python
# Encoding
bencode(42)           → b"i42e"
bencode("hello")      → b"5:hello"
bencode([1, 2])       → b"li1ei2ee"
bencode({"a": 1})     → b"d1:ai1ee"

# Decoding
bdecode(b"i42e")      → 42
bdecode(b"5:hello")   → "hello"
```

Human-readable wire format for debugging

---

# Test Suite

Comprehensive tests (909 lines total)

```
tests/
├── test_raftstate.py    # 647 lines - State machine tests
├── test_raftlog.py      # 99 lines - Log operations
├── test_rafthelpers.py  # 42 lines - Encoding/decoding
└── test_raftmessage.py  # 18 lines - Message types
```

Tests use examples directly from the Raft paper

---

# Next Up

How it all works together...
