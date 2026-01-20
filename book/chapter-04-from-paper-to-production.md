# Chapter 4: From Paper to Production

*In which we examine the practical machinery that transforms an algorithm into running code: networking, serialization, threads, and the art of intentional omission.*

---

## The Gap Between Specification and System

The Raft paper describes an algorithm. An algorithm is a precise sequence of steps—but it says nothing about how those steps become messages on a wire, how concurrent operations are coordinated, or how a cluster of processes actually communicates.

This chapter bridges that gap. We'll examine the implementation layer by layer:

- **Configuration**: How servers discover each other
- **Serialization**: How messages become bytes and back
- **Networking**: How bytes flow between servers
- **Threading**: How concurrent operations are coordinated
- **The Server**: How all the pieces combine
- **Testing**: How we verify correctness
- **Omissions**: What we deliberately left out, and why

By the end, you'll understand not just what the code does, but *why* it's structured the way it is.

---

## Architecture Overview

The implementation is organized into layers, each with a clear responsibility:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           RaftServer                                │
│        Combines state, network, and timer into a running server     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐   │
│    │  RaftState  │    │  RaftNode   │    │  threading.Timer    │   │
│    │             │    │             │    │                     │   │
│    │  - log      │    │  - socket   │    │  - election timeout │   │
│    │  - term     │    │  - queues   │    │  - heartbeat        │   │
│    │  - role     │    │  - threads  │    │                     │   │
│    │  - handlers │    │             │    │                     │   │
│    └─────────────┘    └─────────────┘    └─────────────────────┘   │
│           │                  │                     │                │
└───────────│──────────────────│─────────────────────│────────────────┘
            │                  │                     │
            ▼                  ▼                     ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐
    │ raftmessage │    │ rafthelpers │    │    raftconfig       │
    │             │    │             │    │                     │
    │ Message     │    │ Bencode     │    │ ADDRESS_BY_         │
    │ encode/     │    │ encode/     │    │ IDENTIFIER          │
    │ decode      │    │ decode      │    │                     │
    └─────────────┘    └─────────────┘    └─────────────────────┘
```

The separation is deliberate:

- **RaftState** knows nothing about networks or timers—it's pure algorithm
- **RaftNode** knows nothing about Raft—it's pure networking
- **RaftServer** orchestrates both, adding timing behavior

This separation makes testing easier (you can test state logic without networks) and makes the code more understandable (each module has one job).

---

## Configuration: Discovering the Cluster

The simplest module is `raftconfig.py`:

```python
from typing import Dict, Tuple

ADDRESS_BY_IDENTIFIER: Dict[int, Tuple[str, int]] = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

Nine lines of code. A dictionary mapping server identifiers to `(host, port)` pairs.

This is deliberately minimal. A production system would need:

- Dynamic membership (servers joining and leaving)
- Service discovery (DNS, Consul, etcd)
- Configuration reloading

But for understanding Raft, static configuration suffices. The algorithm is the same whether you have 3 servers or 3,000—and static configuration lets us focus on the algorithm.

---

## Serialization: Bencode

Messages must be serialized to bytes for network transmission. The implementation uses **Bencode**, a simple encoding originally created for BitTorrent.

Why Bencode? Several reasons:

1. **Self-delimiting**: You can parse a Bencode value without knowing its length in advance
2. **Simple**: The entire encoder/decoder is 69 lines
3. **Debuggable**: The output is human-readable (mostly)
4. **No dependencies**: Pure Python, no external libraries

### Bencode Format

| Type | Format | Example |
|------|--------|---------|
| Integer | `i<number>e` | `i42e` → `42` |
| String | `<length>:<string>` | `3:foo` → `"foo"` |
| List | `l<items>e` | `li1e3:fooe` → `[1, "foo"]` |
| Dict | `d<pairs>e` | `d3:fooi1ee` → `{"foo": 1}` |

The encoder in `rafthelpers.py`:

```python
def encode_item(element):
    if element is None:
        return ""

    match type(element):
        case builtins.int:
            return f"i{str(element)}e"

        case builtins.str:
            return f"{len(element)}:{element}"

        case builtins.list:
            return "l" + "".join([encode_item(item) for item in element]) + "e"

        case builtins.dict:
            collection = []
            for pair in sorted(element.items()):
                for item in pair:
                    collection.append(item)
            return "d" + "".join([encode_item(item) for item in collection]) + "e"
```

Note that dictionaries are sorted by key. This ensures deterministic output—the same message always produces the same bytes.

The decoder uses a closure for recursive parsing:

```python
def decode_item(string):
    def closure(string):
        if string == "":
            return None, ""

        elif string.startswith("i"):
            match = re.match("i(-?\\d+)e", string)
            return int(match.group(1)), string[match.span()[1]:]

        elif string[0] in "0123456789":
            match = re.match("(\\d+):", string)
            start = match.span()[1]
            end = start + int(match.group(1))
            return string[start:end], string[end:]

        elif string[0] in {"l", "d"}:
            elements = []
            rest = string[1:]
            while not rest.startswith("e"):
                element, rest = closure(rest)
                elements.append(element)
            rest = rest[1:]

            if string.startswith("l"):
                return elements, rest
            return {k: v for k, v in zip(elements[::2], elements[1::2])}, rest

    return closure(string)[0]
```

The closure returns both the parsed value and the remaining unparsed string, enabling recursive descent through nested structures.

### Testing Serialization

The test suite verifies encoding and decoding are inverses:

```python
def test_encode_items():
    assert rafthelpers.encode_item(None) == ""
    assert rafthelpers.encode_item("") == "0:"
    assert rafthelpers.encode_item([]) == "le"
    assert rafthelpers.encode_item({}) == "de"
    assert rafthelpers.encode_item(1) == "i1e"
    assert rafthelpers.encode_item(-1) == "i-1e"
    assert rafthelpers.encode_item({"foo": {"bar": "baz"}}) == "d3:food3:bar3:bazee"

def test_decode_items():
    assert rafthelpers.decode_item("d3:food3:bar3:bazee") == {"foo": {"bar": "baz"}}
```

---

## Message Types and Encoding

The `raftmessage.py` module defines typed message classes and handles their serialization.

### Message Classes

Each RPC has a corresponding dataclass:

```python
@dataclasses.dataclass
class Message:
    source: int
    target: int

@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int
    previous_index: int
    previous_term: int
    entries: List[raftlog.LogEntry]
    commit_index: int

@dataclasses.dataclass
class AppendEntryResponse(Message):
    current_term: int
    success: bool
    entries_length: int

@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int
    last_log_index: int
    last_log_term: int

@dataclasses.dataclass
class RequestVoteResponse(Message):
    success: bool
    current_term: int
```

Using dataclasses provides:

- Automatic `__init__`, `__repr__`, `__eq__`
- Type annotations for documentation
- Clean attribute access

### Message Encoding

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

        case AppendEntryResponse():
            attributes["message_type"] = MessageType.APPEND_RESPONSE.value
            attributes["success"] = int(attributes["success"])  # bool → int

        case RequestVoteRequest():
            attributes["message_type"] = MessageType.VOTE_REQUEST.value

        case RequestVoteResponse():
            attributes["message_type"] = MessageType.VOTE_RESPONSE.value
            attributes["success"] = int(attributes["success"])
        # ... other cases ...

    return rafthelpers.encode_item(attributes)
```

Note the special handling:

- **Log entries** are converted to dictionaries
- **Booleans** are converted to integers (Bencode doesn't have a bool type)
- **Message type** is added as a discriminator field

A complete encoded message:

```python
message = AppendEntryRequest(1, 2, 3, 4, 5, [LogEntry(5, "a"), LogEntry(6, "b")], -1)

encoded = (
    "d12:commit_indexi-1e12:current_termi3e"
    "7:entriesld4:item1:a4:termi5eed4:item1:b4:termi6eee"
    "12:message_type14:APPEND_REQUEST14:previous_indexi4e13:previous_termi5e"
    "6:sourcei1e6:targeti2ee"
)
```

The result is verbose but readable—you can debug by inspecting the wire format directly.

### Message Decoding

Decoding reverses the process:

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
        # ... other cases ...
```

The `**attributes` syntax unpacks the dictionary into constructor arguments, matching each key to its corresponding parameter.

---

## The Network Layer

`RaftNode` provides the network abstraction. Its design philosophy is stated in the docstring:

> There is no guarantee of message delivery.

This isn't a limitation—it's a feature. Raft is designed for unreliable networks. By providing no delivery guarantees at the network layer, we force the algorithm to handle lost messages correctly.

### Architecture

Each node maintains:

```python
@dataclasses.dataclass
class RaftNode:
    identifier: int

    def __post_init__(self) -> None:
        self.socket: socket.socket = initialize_socket(self.identifier)
        self.incoming: queue.Queue = queue.Queue()
        self.outgoing: Dict[int, queue.Queue] = {
            i: queue.Queue() for i in raftconfig.ADDRESS_BY_IDENTIFIER
        }
```

- **One listening socket**: Accepts incoming connections
- **One incoming queue**: All received messages land here
- **One outgoing queue per peer**: Messages destined for each server

```
                    ┌─────────────────────────────────────┐
                    │              RaftNode               │
                    │                                     │
   incoming         │    ┌──────────────────────────┐    │
   connections ────▶│───▶│     incoming queue       │    │
                    │    └──────────────────────────┘    │
                    │                                     │
                    │    ┌──────────────────────────┐    │   ──▶ to server 1
                    │    │  outgoing queue (srv 1)  │────│
                    │    ├──────────────────────────┤    │   ──▶ to server 2
                    │    │  outgoing queue (srv 2)  │────│
                    │    ├──────────────────────────┤    │   ──▶ to server 3
                    │    │  outgoing queue (srv 3)  │────│
                    │    └──────────────────────────┘    │
                    │                                     │
                    └─────────────────────────────────────┘
```

### The Listening Thread

The `listen` method runs in a background thread, accepting connections and spawning handlers:

```python
def listen(self) -> None:
    """
    Run in background thread to listen for incoming connections and places
    messages in incoming queue.
    """
    while True:
        client, address = self.socket.accept()
        threading.Thread(target=self._listen, args=(client,)).start()
```

Each connection gets its own handler thread:

```python
def _listen(self, client: socket.socket) -> None:
    try:
        while True:
            length = int.from_bytes(client.recv(4), byteorder="big")

            if length == 0:
                raise IOError

            message = client.recv(length).decode("ascii")
            self.incoming.put(message)

    except IOError:
        client.close()
```

Messages are length-prefixed: 4 bytes for the length (big-endian), then the message bytes. This framing is necessary because TCP is a stream protocol—without framing, you can't tell where one message ends and the next begins.

### The Delivery Threads

Each outgoing queue has a dedicated delivery thread:

```python
def deliver(self, identifier: int) -> None:
    """
    Run in background thread to deliver outgoing messages to other nodes.
    The delivery is best-efforts, in which the message is discarded if the
    remote server is not operational.
    """
    sock = None
    address = raftconfig.ADDRESS_BY_IDENTIFIER[identifier]

    try:
        while True:
            message = self.outgoing[identifier].get()
            sock = self._deliver(sock, address, message)

    finally:
        print("panic!")
        os._exit(1)
```

The `_deliver` method handles connection management:

```python
def _deliver(
    self, sock: Optional[socket.socket], address: Tuple[str, int], message: bytes
) -> Optional[socket.socket]:
    try:
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(address)

        sock.sendall(len(message).to_bytes(4, byteorder="big"))
        sock.sendall(message)

    except Exception as e:
        print(e)
        sock = None

    return sock
```

Key design choices:

1. **Connection reuse**: The socket is kept open between messages. If sending fails, it's reset to `None` and a new connection will be established.

2. **Best-effort delivery**: If the remote server is down, the message is silently dropped. No retries, no buffering.

3. **Panic on thread failure**: If a delivery thread exits unexpectedly, the entire process terminates. This prevents subtle partial failures.

### The Public Interface

The API is minimal:

```python
def send(self, identifier: int, message: str) -> None:
    self.outgoing[identifier].put(message.encode("ascii"))

def receive(self) -> str:
    return self.incoming.get()
```

`send` is non-blocking—it puts the message in a queue and returns immediately. `receive` is blocking—it waits until a message arrives.

---

## The Server: Orchestrating Everything

`RaftServer` combines state, networking, and timing:

```python
@dataclasses.dataclass
class RaftServer:
    identifier: int

    def __post_init__(self) -> None:
        self.state: raftstate.RaftState = raftstate.RaftState(self.identifier)
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)
        self.timer: threading.Timer = threading.Timer(TIMEOUT, self.timeout)
        self.reset: bool = True
```

### The Timeout Mechanism

The timer implements election timeouts and heartbeat schedules:

```python
TIMEOUT = 3  # seconds

def cycle(self) -> None:
    timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

    self.timer.cancel()
    self.timer = threading.Timer(timeout, self.timeout)
    self.timer.start()

    self.reset = True
```

Leaders use a shorter timeout (3 seconds) for heartbeats. Followers and candidates use a longer timeout (6 seconds) for election detection.

When the timeout fires:

```python
def timeout(self) -> None:
    # Random delay before elections
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)

    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))

    self.cycle()
```

The timeout generates an internal message (RoleChange or heartbeat) and injects it into the incoming queue. This elegant design means all state changes flow through the same message-handling path.

### The Reset Flag

The `reset` flag prevents unnecessary elections:

```python
def respond(self) -> None:
    while True:
        payload = self.node.receive()
        request = raftmessage.decode_message(payload)

        # Suppress timeout-triggered state change if we received
        # a relevant message this cycle
        if (self.state.role, type(request)) in [
            (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
            (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
            (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
        ]:
            self.reset = False

        response = self.state.handle_message(request)
        self.send(response)
```

If a follower receives a heartbeat, it sets `reset = False`. When the timeout fires, it checks this flag and skips the state change if the flag is false. This prevents followers from starting elections while they're successfully receiving heartbeats.

### Visual Feedback

The server provides color-coded terminal output:

```python
def color(self) -> str:
    return raftrole.color(self.state.role)

# In raftrole.py:
def color(role: Role) -> str:
    match role:
        case Role.LEADER:
            return "\033[32m"  # Green

        case Role.CANDIDATE:
            return "\033[93m"  # Yellow

        case Role.FOLLOWER:
            return "\033[31m"  # Red
```

When running a cluster, you can instantly see each server's role by its prompt color:

- **Red**: Follower (passive, waiting)
- **Yellow**: Candidate (seeking votes)
- **Green**: Leader (in charge)

---

## The Client

`RaftClient` provides a simple interface for interacting with the cluster:

```python
@dataclasses.dataclass
class RaftClient:
    identifier: int

    def __post_init__(self) -> None:
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)

    def instruct(self) -> None:
        while True:
            prompt = input(f"{self.identifier} > ")

            if prompt == "self":
                # Send debug command to all servers
                self.send([
                    raftmessage.Text(self.identifier, target, prompt)
                    for target in raftconfig.ADDRESS_BY_IDENTIFIER
                ])
                continue

            target, command = int(prompt[0]), prompt[2:]

            if command.startswith("append"):
                # Parse: "1 append a b c" → entries a, b, c to server 1
                for item in command.replace("append ", "").split():
                    messages.append(
                        raftmessage.ClientLogAppend(self.identifier, target, item)
                    )
```

The client commands:

| Command | Effect |
|---------|--------|
| `self` | All servers print their state |
| `1 append a b c` | Server 1 appends entries "a", "b", "c" |

The `self` command is invaluable for debugging—it shows each server's current term, log, commit index, and other state.

---

## Testing Strategies

The test suite uses several strategies to verify correctness.

### Unit Tests for Serialization

```python
def test_message_translation():
    message = raftmessage.AppendEntryRequest(
        1, 2, 3, 4, 5, [raftlog.LogEntry(5, "a"), raftlog.LogEntry(6, "b")], -1
    )

    string = (
        "d12:commit_indexi-1e12:current_termi3e"
        + "7:entriesld4:item1:a4:termi5eed4:item1:b4:termi6eee"
        + "12:message_type14:APPEND_REQUEST14:previous_indexi4e13:previous_termi5e"
        + "6:sourcei1e6:targeti2ee"
    )

    assert raftmessage.encode_message(message) == string
    assert raftmessage.decode_message(string) == message
```

This verifies that encoding and decoding are inverses—a message survives the round trip unchanged.

### Paper-Based Test Fixtures

The Raft paper's Figure 7 shows logs in various states of divergence. The test suite recreates these:

```python
@pytest.fixture
def paper_log():
    paper_log = [
        raftlog.LogEntry(1, "1"),
        raftlog.LogEntry(1, "1"),
        raftlog.LogEntry(1, "1"),
    ]
    paper_log += [raftlog.LogEntry(4, "4"), raftlog.LogEntry(4, "4")]
    paper_log += [raftlog.LogEntry(5, "5"), raftlog.LogEntry(5, "5")]
    paper_log += [
        raftlog.LogEntry(6, "6"),
        raftlog.LogEntry(6, "6"),
        raftlog.LogEntry(6, "6"),
    ]
    return paper_log
```

This direct correspondence between tests and paper makes verification tractable: you can point to a specific scenario in the paper and trace it through the code.

### State Machine Tests

Most tests operate on `RaftState` directly, bypassing networking:

```python
def test_handle_message_a(paper_log, logs_by_identifier):
    leader_state, follower_state, _, request = init_raft_states(
        paper_log, logs_by_identifier["a"], None
    )

    response = follower_state.handle_message(request[0])
    assert not response[0].success

    request = leader_state.handle_message(response[0])
    response = follower_state.handle_message(request[0])
    assert response[0].success
```

This tests the algorithm without network complexity. The `init_raft_states` helper sets up servers in specific configurations, and the test simulates message exchange by calling `handle_message` directly.

### Multi-Server Consensus Test

The `test_consensus` test verifies complete log reconciliation:

```python
def test_consensus(paper_log, logs_by_identifier):
    leader_state, follower_a_state, follower_b_state, request = init_raft_states(
        paper_log, logs_by_identifier["a"], logs_by_identifier["b"]
    )

    # Reconcile both followers
    # ... message exchanges ...

    # Verify all logs match
    assert leader_state.match_index == {1: 9, 2: 9, 3: 9}

    # Verify commit propagates
    assert follower_a_state.commit_index == 9
    assert follower_b_state.commit_index == 9
```

This is an integration test at the state level—multiple servers with divergent logs converging to consistency.

---

## What's Intentionally Omitted

This implementation is complete for its purpose: teaching Raft. But it omits several features required for production use.

### Persistence

The Raft paper specifies persistent state:

> **Persistent state on all servers** (Updated on stable storage before responding to RPCs):
> - currentTerm
> - votedFor
> - log[]

This implementation keeps everything in memory. If a server crashes and restarts, it loses all state.

**Why omit it?** Persistence adds complexity (file formats, fsync semantics, recovery logic) without illuminating the algorithm. The core of Raft—elections, replication, commitment—works identically whether state is persisted or not.

### Log Compaction (Snapshots)

In a long-running system, the log grows without bound. Production implementations periodically snapshot the state machine and discard old log entries.

The paper's Section 7 describes this:

> Snapshotting is the simplest approach to compaction... the entire current system state is written to a snapshot on stable storage, then the entire log up to that point is discarded.

**Why omit it?** Snapshots are an optimization, not part of the core algorithm. They're necessary for practical systems but don't affect correctness of consensus.

### Membership Changes

The paper's Section 6 describes adding and removing servers from a running cluster. This is notoriously subtle—getting it wrong can create split-brain.

**Why omit it?** Membership changes are complex enough to deserve their own chapter. The implementation uses static configuration precisely to avoid this complexity while teaching the core algorithm.

### State Machine

The paper describes applying committed entries to a state machine:

> Once a leader has committed a log entry, it applies the entry to its own state machine and returns the result to the client.

This implementation has no state machine. Committed entries are simply... committed. Nothing happens with them.

**Why omit it?** The state machine is application-specific. A key-value store, a lock service, a configuration system—each would have different state machines. By omitting it, we keep focus on consensus, which is the same regardless of application.

### Client Interaction

The paper discusses client request handling:

> If the leader crashes after committing the log entry but before responding to the client, the client will retry the command with a new leader.

This requires:
- Client session tracking
- Duplicate detection
- Linearizable semantics

**Why omit it?** These are important for real systems but orthogonal to consensus. The implementation's client is a debugging tool, not a production interface.

---

## Design Decisions

Several design decisions merit discussion.

### Messages as Internal Events

The implementation routes all state changes through the message handling system:

```python
def timeout(self) -> None:
    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))
```

Timeout events become messages. This means `handle_message` is the single entry point for all state changes. Benefits:

1. **Uniformity**: One code path for all state transitions
2. **Testability**: Tests can inject any message type
3. **Debuggability**: All events appear in message logs

### Meta-Roles for Internal Transitions

The `TIMER`, `ELECTION_COMMISSION`, and `CONSTITUTION` meta-roles model non-network state changes:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
    TIMER = "TIMER"                    # Triggers follower → candidate
    ELECTION_COMMISSION = "ELECTION_COMMISSION"  # Certifies candidate → leader
    CONSTITUTION = "CONSTITUTION"      # Forces leader → follower
```

This allows all transitions to flow through `enumerate_state_change`:

```python
def change_role(self, from_role, to_role, current_term=None):
    match from_role:
        case raftrole.Role.FOLLOWER:
            source_role = raftrole.Role.TIMER
        case raftrole.Role.CANDIDATE:
            source_role = raftrole.Role.ELECTION_COMMISSION
        case raftrole.Role.LEADER:
            source_role = raftrole.Role.CONSTITUTION

    state_change = raftrole.enumerate_state_change(
        source_role, current_term, from_role, current_term
    )
    self.implement_state_change(state_change)
```

The metaphor is apt: a timer starts elections, an election commission certifies winners, and a constitution defines when leaders must step down.

### Experimental Mode

The `experimental_mode` flag disables the current-term requirement for commits:

```python
if update_commit_index or self.experimental_mode:
    self.commit_index = potential_commit_index
```

This exists solely for the safety demonstration in `test_commit_without_requirement`. It shows what goes wrong without the safety rule—educational value through intentional breakage.

---

## Running the Cluster

To experience Raft in action:

### Start the Servers

In three terminals:

```bash
# Terminal 1
$ python src/raftserver.py 1
start.
1 >    # Red prompt (follower)

# Terminal 2
$ python src/raftserver.py 2
start.
2 >    # Red prompt (follower)

# Terminal 3
$ python src/raftserver.py 3
start.
3 >    # Red prompt (follower)
```

### Watch an Election

After ~6 seconds, one server's prompt turns yellow (candidate), then green (leader). The others remain red.

### Start the Client

```bash
# Terminal 4
$ python src/raftclient.py 0
0 >
```

### Append Entries

```bash
0 > 1 append x y z
```

This sends entries "x", "y", "z" to server 1. If server 1 is the leader, it will replicate them; otherwise, nothing happens (the implementation doesn't redirect to the leader).

### Inspect State

```bash
0 > self
```

Each server prints its state:

```
commit_index: 2
config: {1: ('localhost', 7000), 2: ('localhost', 8000), 3: ('localhost', 9000)}
current_term: 3
current_votes: None
experimental_mode: False
has_followers: True
identifier: 1
log: [LogEntry(3, 'x'), LogEntry(3, 'y'), LogEntry(3, 'z')]
match_index: {1: 2, 2: 2, 3: 2}
next_index: {1: 3, 2: 3, 3: 3}
role: Role.LEADER
voted_for: 1
```

### Kill and Restart

Press Ctrl-C to kill the leader. Watch the remaining servers elect a new leader. Restart the killed server and observe it rejoin as a follower.

---

## What We've Learned

This chapter examined the practical machinery beneath the Raft algorithm:

- **Configuration** is deliberately minimal—static addresses for a 3-node cluster
- **Bencode** provides simple, debuggable serialization
- **Message classes** give type safety and clear structure
- **The network layer** provides best-effort delivery over TCP
- **Threading** separates concerns: listening, delivering, timing
- **The server** orchestrates everything through message passing
- **Testing** uses paper-based fixtures for traceability
- **Omissions** are intentional—the implementation focuses on consensus

The architecture reflects a key insight: **separation of concerns enables understanding**. By keeping `RaftState` pure (no I/O), `RaftNode` generic (no Raft knowledge), and `RaftServer` thin (just orchestration), each component can be understood in isolation.

---

## Conclusion: What You've Learned

Across four chapters, we've journeyed from the problem of consensus to a working implementation:

**Chapter 1** introduced consensus as the problem of getting multiple computers to agree despite failures. We met Raft's core abstractions: terms, roles, and the replicated log.

**Chapter 2** explored leader election—how candidates solicit votes, how servers decide whether to grant them, and how randomized timeouts prevent livelock.

**Chapter 3** examined log replication—the heartbeat mechanism, the consistency check, backtracking to find match points, and the subtle safety rule for commitment.

**Chapter 4** connected algorithm to implementation—serialization, networking, threading, and the design decisions that make theory into running code.

### The Power of Decomposition

Raft's genius lies in decomposition. By separating consensus into election and replication, each piece becomes tractable. By separating implementation into state and networking, each layer becomes testable.

This decomposition isn't just pedagogical—it's practical. When debugging a distributed system, you need to isolate problems. Is the issue in the consensus algorithm or the network layer? In election logic or replication? Clean separation makes these questions answerable.

### From Here

If you've worked through these chapters—read the code, run the cluster, traced through the scenarios—you now understand Raft at a level few engineers achieve. You can:

- Read the Raft paper and map every rule to implementation
- Predict how the system behaves under various failure scenarios
- Debug consensus issues by reasoning about state transitions
- Evaluate production Raft implementations (etcd, Consul, CockroachDB) with informed judgment

The algorithm is just the beginning. Production systems add persistence, snapshots, membership changes, linearizable client semantics, and countless optimizations. But all of these build on the foundation you now have.

---

## Exercises

1. **Add Persistence**: Modify `RaftState` to write `current_term`, `voted_for`, and `log` to a file after each state change. Modify `__post_init__` to load from the file if it exists. Test by killing and restarting servers.

2. **Implement a State Machine**: Add a simple key-value store. When entries are committed, apply them to the store. Add a client command to query the store.

3. **Connection Pooling**: The current implementation creates a new connection if the previous one failed. Modify `_deliver` to implement exponential backoff on connection failures.

4. **Batch Backtracking**: Modify `handle_append_entries_response` to skip multiple indices on failure. The follower should return information about where its log diverges.

5. **Chaos Testing**: Write a script that randomly kills and restarts servers while the client continuously appends entries. Verify that all servers eventually have identical logs.

6. **Metrics**: Add counters for: messages sent, messages received, elections started, elections won, entries replicated, entries committed. Print these on the `self` command.

---

## Further Reading

**The Raft Paper**
Ongaro, D., & Ousterhout, J. (2014). "In Search of an Understandable Consensus Algorithm."
The extended version includes proofs and additional discussion.

**The Raft Dissertation**
Ongaro, D. (2014). "Consensus: Bridging Theory and Practice."
300+ pages of detail, including cluster membership changes and log compaction.

**etcd/raft**
https://github.com/etcd-io/raft
A production-quality Go implementation used by Kubernetes.

**Designing Data-Intensive Applications**
Kleppmann, M. (2017). O'Reilly Media.
Chapter 9 places Raft in the broader context of distributed systems.

**David Beazley's Rafting Trip**
https://www.dabeaz.com/raft.html
The course that produced this implementation.

---

*The best way to understand a distributed system is to build one. You've now done that. Take what you've learned and build something that matters.*
