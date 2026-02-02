# Chapter 7: Message Types and the Handler Pattern

## Introduction

This chapter covers how the implementation structures communication between nodes. Rather than using direct RPC calls, nodes exchange typed messages. Each message type has a corresponding handler in `RaftState`. This message-driven design enables deterministic testing and cleanly separates protocol logic from network I/O.

## 7.1 The Message Base Class

All messages inherit from a common base class:

```python
@dataclasses.dataclass
class Message:
    source: int
    target: int
```

Every message carries:
- `source`: The identifier of the sending node
- `target`: The identifier of the receiving node

This base class enables uniform handling—the dispatch logic can route any message without knowing its specific type.

## 7.2 Message Types Overview

The implementation defines eight message types:

```python
class MessageType(enum.Enum):
    CLIENT_LOG_APPEND = "CLIENT_LOG_APPEND"
    UPDATE_FOLLOWERS = "UPDATE_FOLLOWERS"
    APPEND_REQUEST = "APPEND_REQUEST"
    APPEND_RESPONSE = "APPEND_RESPONSE"
    RUN_ELECTION = "RUN_ELECTION"
    VOTE_REQUEST = "VOTE_REQUEST"
    VOTE_RESPONSE = "VOTE_RESPONSE"
    ROLE_CHANGE = "ROLE_CHANGE"
    TEXT = "TEXT"
```

| Type | Direction | Purpose |
|------|-----------|---------|
| `ClientLogAppend` | Client → Leader | Request to append an entry |
| `UpdateFollowers` | Internal | Trigger heartbeat to all followers |
| `AppendEntryRequest` | Leader → Follower | Replicate log entries |
| `AppendEntryResponse` | Follower → Leader | Acknowledge replication |
| `RunElection` | Internal | Trigger vote solicitation |
| `RequestVoteRequest` | Candidate → All | Request a vote |
| `RequestVoteResponse` | All → Candidate | Grant or deny vote |
| `RoleChange` | Internal | Trigger role transition |
| `Text` | Any | Debugging (expose state) |

## 7.3 External vs. Internal Messages

Some messages cross the network between nodes:

```python
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int
    previous_index: int
    previous_term: int
    entries: List[raftlog.LogEntry]
    commit_index: int

@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int
    last_log_index: int
    last_log_term: int
```

Others are internal triggers that never leave the node:

```python
@dataclasses.dataclass
class UpdateFollowers(Message):
    followers: List[int]

@dataclasses.dataclass
class RunElection(Message):
    followers: List[int]

@dataclasses.dataclass
class RoleChange(Message):
    from_role: raftrole.Role
    to_role: raftrole.Role
```

Why use messages for internal events? It keeps all state changes flowing through the same `handle_message` dispatch. This uniformity simplifies testing and debugging—you can trace every state change to a specific message.

## 7.4 The Handler Pattern

The `handle_message` method dispatches messages to type-specific handlers:

```python
def handle_message(self, message: raftmessage.Message) -> List[raftmessage.Message]:
    match message:
        case raftmessage.ClientLogAppend():
            return self.handle_client_log_append(**vars(message))

        case raftmessage.UpdateFollowers():
            return self.handle_leader_heartbeat(**vars(message))

        case raftmessage.AppendEntryRequest():
            return self.handle_append_entries_request(**vars(message))

        case raftmessage.AppendEntryResponse():
            return self.handle_append_entries_response(**vars(message))

        case raftmessage.RunElection():
            return self.handle_candidate_solicitation(**vars(message))

        case raftmessage.RequestVoteRequest():
            return self.handle_request_vote_request(**vars(message))

        case raftmessage.RequestVoteResponse():
            return self.handle_request_vote_response(**vars(message))

        case raftmessage.RoleChange():
            return self.handle_role_change(**vars(message))

        case raftmessage.Text():
            return self.handle_text(**vars(message))

        case _:
            raise Exception(
                "Exhaustive switch error on message type with message {message}."
            )
```

Key design points:

1. **Pattern matching**: Python 3.10's `match` statement ensures every message type is handled
2. **Attribute unpacking**: `**vars(message)` passes message fields as keyword arguments
3. **Response messages**: Handlers return a list of messages to send (may be empty)
4. **Exhaustive matching**: The `case _` default raises an exception for unknown types

## 7.5 Message Details

**AppendEntryRequest** carries everything needed for log replication:

```python
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int      # Leader's term
    previous_index: int    # Index before new entries
    previous_term: int     # Term of previous entry
    entries: List[raftlog.LogEntry]  # Entries to append
    commit_index: int      # Leader's commit index
```

**AppendEntryResponse** reports success or failure:

```python
@dataclasses.dataclass
class AppendEntryResponse(Message):
    current_term: int    # Follower's term (for leader to update)
    success: bool        # Did append succeed?
    entries_length: int  # How many entries were sent (for index update)
```

**RequestVoteRequest** contains candidate information:

```python
@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int     # Candidate's term
    last_log_index: int   # Index of candidate's last entry
    last_log_term: int    # Term of candidate's last entry
```

**RequestVoteResponse** grants or denies the vote:

```python
@dataclasses.dataclass
class RequestVoteResponse(Message):
    success: bool       # Vote granted?
    current_term: int   # Voter's term
```

## 7.6 Message Encoding and Decoding

Messages must be serialized for network transmission. Building on the Bencode primitives from Chapter 4, the `encode_message` function converts a message to a Bencode string:

```python
def encode_message(message: Message) -> str:
    attributes = vars(message).copy()

    match message:
        case AppendEntryRequest():
            entries = []
            for entry in message.entries:
                entries.append(vars(entry))
            attributes["message_type"] = MessageType.APPEND_REQUEST.value
            attributes["entries"] = entries

        case AppendEntryResponse():
            attributes["message_type"] = MessageType.APPEND_RESPONSE.value
            attributes["success"] = int(attributes["success"])  # bool → int

        case RequestVoteResponse():
            attributes["message_type"] = MessageType.VOTE_RESPONSE.value
            attributes["success"] = int(attributes["success"])

        case RoleChange():
            attributes["message_type"] = MessageType.ROLE_CHANGE.value
            attributes["from_role"] = attributes["from_role"].value
            attributes["to_role"] = attributes["to_role"].value

        # ... other cases

    return rafthelpers.encode_item(attributes)
```

Notable transformations:
- Add `message_type` for dispatch on decode
- Convert booleans to integers (Bencode has no boolean type)
- Convert enums to their string values
- Convert nested objects (LogEntry) to dictionaries

The `decode_message` function reverses these transformations:

```python
def decode_message(string: str) -> Message:
    attributes = rafthelpers.decode_item(string)
    message_type = MessageType(attributes["message_type"])
    del attributes["message_type"]

    match message_type:
        case MessageType.APPEND_REQUEST:
            entries = []
            for entry in attributes["entries"]:
                entries.append(raftlog.LogEntry(**entry))
            attributes["entries"] = entries
            return AppendEntryRequest(**attributes)

        case MessageType.APPEND_RESPONSE:
            attributes["success"] = bool(attributes["success"])
            return AppendEntryResponse(**attributes)

        # ... other cases
```

## 7.7 Testing with Messages

The message-driven design enables testing without network:

```python
def test_handle_message_a(paper_log, logs_by_identifier):
    leader_state, follower_state, _, request = init_raft_states(
        paper_log, logs_by_identifier["a"], None
    )

    # Send request directly to follower handler
    response = follower_state.handle_message(request[0])
    assert not response[0].success

    # Send response directly to leader handler
    request = leader_state.handle_message(response[0])
    response = follower_state.handle_message(request[0])
    assert response[0].success
```

No sockets, no threads, no timing issues. You can test the exact message sequence that causes a bug, then verify the fix.

## 7.8 Why Messages, Not Methods?

Why not have the leader call `follower.append_entries(...)` directly?

**Decoupling**: The protocol layer doesn't know about network topology. It just produces and consumes messages.

**Testing**: You can feed any sequence of messages and check responses. No need to mock network calls.

**Debugging**: Messages are data. You can log them, serialize them, replay them.

**Asynchrony**: The real system is asynchronous. Messages might be delayed, reordered, or lost. The message model makes this explicit.

## Conclusion

The implementation communicates through typed messages dispatched by `handle_message`. Each of the eight message types corresponds to a specific protocol operation. Internal messages (like `UpdateFollowers` and `RoleChange`) keep all state changes flowing through the same dispatch path. Handlers return response messages, creating a pure interface that enables deterministic testing of the protocol without network infrastructure.
