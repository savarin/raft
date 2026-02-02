# Chapter 7: Message Types and the Handler Pattern

## Introduction

This chapter covers how the implementation structures communication between nodes. Rather than using direct RPC calls, nodes exchange typed messages. Each message type has a corresponding handler in `RaftState`. This message-driven design enables deterministic testing and cleanly separates protocol logic from network I/O.

## Sections

### 7.1 The Message Base Class

All messages inherit from `Message`, carrying source and target identifiers:

```python
@dataclasses.dataclass
class Message:
    source: int
    target: int
```

### 7.2 Message Types Overview

The eight message types in `raftmessage.py`:

| Type | Purpose |
|------|---------|
| `ClientLogAppend` | Client requests leader to append entry |
| `UpdateFollowers` | Internal: trigger heartbeat to followers |
| `AppendEntryRequest` | Leader → Follower: replicate entries |
| `AppendEntryResponse` | Follower → Leader: acknowledge entries |
| `RunElection` | Internal: trigger vote solicitation |
| `RequestVoteRequest` | Candidate → Others: request vote |
| `RequestVoteResponse` | Others → Candidate: grant/deny vote |
| `RoleChange` | Internal: trigger role transition |

### 7.3 External vs. Internal Messages

Some messages cross the network (`AppendEntryRequest`, `RequestVoteResponse`). Others are internal triggers (`UpdateFollowers`, `RunElection`, `RoleChange`). Both flow through the same `handle_message` dispatch.

### 7.4 The Handler Pattern

`handle_message` uses pattern matching to dispatch:

```python
def handle_message(self, message: raftmessage.Message) -> List[raftmessage.Message]:
    match message:
        case raftmessage.AppendEntryRequest():
            return self.handle_append_entries_request(**vars(message))
        case raftmessage.RequestVoteRequest():
            return self.handle_request_vote_request(**vars(message))
        # ...
```

Handlers return a list of response messages (possibly empty).

### 7.5 Message Encoding and Decoding

How `encode_message` and `decode_message` in `raftmessage.py` use the Bencode helpers. Handling special cases: boolean success flags, log entry lists, role enums.

### 7.6 Why Messages, Not Methods

The message-driven approach enables:
- Testing without network: feed messages directly, check responses
- Clear protocol boundaries: all communication is explicit
- Easy logging and debugging: messages are inspectable data

## Conclusion

The implementation communicates through typed messages dispatched by `handle_message`. This pattern separates the "what" (message data) from the "how" (network transmission). Handlers return response messages, creating a pure function interface that enables deterministic testing of the protocol.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- `Message` base class
- All eight message types
- External vs. internal messages
- `handle_message` dispatch pattern
- `encode_message` / `decode_message`
- Benefits of message-driven design

**Back-references**:
- Chapter 2 introduced message-driven architecture conceptually
- Chapter 4 covered Bencode encoding used by message serialization

**Forward dependencies**:
- Chapter 8 covers `RequestVoteRequest/Response` handlers in detail
- Chapter 9 covers `AppendEntryRequest/Response` handlers in detail
- Chapter 10 shows how messages flow over the network
