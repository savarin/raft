# Chapter 3: Messages

Raft servers communicate through a defined set of messages. This chapter catalogs those message types, explains what each one does, and shows how they map to the RPCs described in the Raft paper.

Messages are the vocabulary of Raft. After this chapter, you'll recognize an `AppendEntryRequest` or `RequestVoteResponse` and know its purpose. The state machine chapter (Chapter 5) shows how these messages are processed; this chapter focuses on what they contain.

## The Message Hierarchy

Every message has a source and a target:

```python
@dataclasses.dataclass
class Message:
    source: int
    target: int
```

The source is the server sending the message; the target is the server receiving it. Server identifiers are integers (1, 2, 3 in a three-node cluster).

Why include both? Because messages cross the network asynchronously. When a response arrives, the receiver needs to know which server it came from. And when a server handles a request, it needs to know where to send the response.

All other message types inherit from `Message` and add their own fields.

## AppendEntries Messages

The AppendEntries RPC is the leader's main tool. It replicates log entries to followers and serves as a heartbeat to maintain leadership.

### AppendEntryRequest

```python
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int
    previous_index: int
    previous_term: int
    entries: List[raftlog.LogEntry]
    commit_index: int
```

These fields map directly to Figure 2 of the Raft paper:

- **current_term**: The leader's term. Followers use this to detect stale leaders.
- **previous_index**: Index of the log entry immediately before the new entries. Used for the consistency check.
- **previous_term**: Term of the entry at previous_index. Also used for the consistency check.
- **entries**: The log entries to append. Empty for heartbeats—the leader sends these periodically even with nothing new.
- **commit_index**: The leader's commit index. Followers advance their own commit index to match (but not past their log length).

When entries is empty, the message is a heartbeat. When non-empty, it's log replication. The same message type serves both purposes.

### AppendEntryResponse

```python
@dataclasses.dataclass
class AppendEntryResponse(Message):
    current_term: int
    success: bool
    entries_length: int
```

- **current_term**: The follower's term. If higher than the leader's, the leader steps down.
- **success**: True if the append succeeded. False means the consistency check failed—the follower's log doesn't have an entry at previous_index with the expected term.
- **entries_length**: How many entries were in the request. The leader uses this to update its tracking of the follower's progress.

On failure, the leader decrements its tracked `nextIndex` for this follower and retries with earlier entries. Eventually, the logs converge.

## RequestVote Messages

The RequestVote RPC is how candidates gather votes during elections.

### RequestVoteRequest

```python
@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int
    last_log_index: int
    last_log_term: int
```

- **current_term**: The candidate's term. Voters reject candidates with stale terms.
- **last_log_index**: Index of the candidate's last log entry.
- **last_log_term**: Term of the candidate's last log entry.

The log information determines "up-to-dateness." A voter rejects candidates whose logs are behind its own. This ensures the elected leader has all committed entries—a key safety property.

### RequestVoteResponse

```python
@dataclasses.dataclass
class RequestVoteResponse(Message):
    success: bool
    current_term: int
```

- **success**: True if the vote is granted.
- **current_term**: The voter's term. If higher than the candidate's, the candidate steps down.

A candidate wins if it gets votes from a majority of servers in its term. Until then, it keeps collecting responses.

## Internal Messages

Some messages never cross the network. They represent internal events wrapped as messages so the state machine can handle them uniformly.

### ClientLogAppend

```python
@dataclasses.dataclass
class ClientLogAppend(Message):
    item: str
```

A client command to append an entry. Only the leader accepts these. The `item` is the command data.

### UpdateFollowers

```python
@dataclasses.dataclass
class UpdateFollowers(Message):
    followers: List[int]
```

A trigger for the leader to send heartbeats. When this message is processed, the leader sends `AppendEntryRequest` to each follower.

### RunElection

```python
@dataclasses.dataclass
class RunElection(Message):
    followers: List[int]
```

A trigger for a candidate to request votes. When processed, the candidate sends `RequestVoteRequest` to each other server.

### RoleChange

```python
@dataclasses.dataclass
class RoleChange(Message):
    from_role: raftrole.Role
    to_role: raftrole.Role
```

A timeout-driven role transition. When a follower times out, it receives a `RoleChange(FOLLOWER, CANDIDATE)` message to process. This keeps timeout handling in the same message-processing pipeline as everything else.

### Text

```python
@dataclasses.dataclass
class Text(Message):
    text: str
```

A debug message for querying server state. The `self` command from the client uses this.

## The MessageType Enum

For serialization, each message needs a type tag:

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

The `encode_message` function adds this tag when serializing; `decode_message` uses it to reconstruct the correct class.

## Bencode Serialization

Messages need to travel over TCP sockets as bytes. This implementation uses Bencode—the encoding from BitTorrent.

Why Bencode? It's simple, unambiguous, and has no external dependencies. The entire encoder/decoder is about 70 lines of Python.

### Encoding Rules

Bencode has four types:

**Integers**: `i<number>e`
```
42      → i42e
-17     → i-17e
```

**Strings**: `<length>:<content>`
```
"hello" → 5:hello
"ab"    → 2:ab
```

**Lists**: `l<elements>e`
```
[1, "a"] → li1e1:ae
```

**Dictionaries**: `d<key><value>...e` (keys sorted alphabetically)
```
{"b": 1, "a": 2} → d1:ai2e1:bi1ee
```

### Encoding Messages

The `encode_message` function converts a message to a Bencode string:

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
        # ... other cases

    return rafthelpers.encode_item(attributes)
```

Each message becomes a dictionary with a `message_type` field plus the message's own fields. `LogEntry` objects need special handling—they're converted to dictionaries of their fields.

Booleans become integers (0 or 1) because Bencode doesn't have a boolean type. Roles become their string values.

### Decoding Messages

The `decode_message` function reverses the process:

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
        # ... other cases
```

It parses the Bencode, extracts the message type, and reconstructs the appropriate class. Entry dictionaries become `LogEntry` objects. Integer booleans become Python booleans. Role strings become `Role` enum values.

### Why This Matters

Serialization bugs cause silent data corruption. If the encoder writes `entries` but the decoder reads `entry`, messages appear to work but contain wrong data. The tests in `test_raftmessage.py` verify round-trip correctness: encode a message, decode it, compare to the original.

The Bencode format is also human-readable (sort of). When debugging, you can look at the raw bytes on the wire and understand what's being sent.

## Conclusion

Nine message types form the complete vocabulary:

- **External RPCs**: `AppendEntryRequest`, `AppendEntryResponse`, `RequestVoteRequest`, `RequestVoteResponse`
- **Internal triggers**: `UpdateFollowers`, `RunElection`, `RoleChange`
- **Client/debug**: `ClientLogAppend`, `Text`

External messages cross the network between servers. Internal messages represent timer-driven events, wrapped as messages for uniform handling. Together they cover every interaction in the Raft protocol.

The state machine (Chapter 5) consumes these messages and produces responses. But first, we need to understand the roles that servers can have—the topic of the next chapter.
