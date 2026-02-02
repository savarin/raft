# Chapter 8: Network and Runtime

The previous chapters explained the Raft algorithm as pure state machine logic. This chapter shows how that logic runs in practice: `RaftNode` for network communication, `RaftServer` for orchestration, and timers for driving elections.

This chapter completes the picture. After reading it, you can trace a message from one server to another, watch state change in response, and understand how timeouts trigger elections. You'll also understand the intentional limitations—what this implementation omits and why.

## The RaftNode Abstraction

`RaftNode` handles network communication. Its interface is simple:

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

    def send(self, identifier: int, message: str) -> None:
        self.outgoing[identifier].put(message.encode("ascii"))

    def receive(self) -> str:
        return self.incoming.get()
```

Two methods matter:

- **send(identifier, message)**: Non-blocking. Queues the message for delivery to the target server. Returns immediately.
- **receive()**: Blocking. Waits until a message arrives from any server. Returns the message.

This interface decouples the state machine from network details. `RaftState` doesn't know about sockets or threads—it just processes messages. `RaftServer` uses `send` and `receive` to connect the state machine to the network.

## Socket Management

Each node binds to an address from the configuration:

```python
def initialize_socket(identifier: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)

    address = raftconfig.ADDRESS_BY_IDENTIFIER.get(identifier, ("localhost", 10000))
    sock.bind(address)
    sock.listen()

    return sock
```

Standard TCP socket setup. The `SO_REUSEADDR` option allows restarting the server quickly without waiting for the old socket to time out.

## Background Threads

The real work happens in background threads. When `node.start()` is called:

```python
def start(self) -> None:
    threading.Thread(target=self.listen, args=()).start()

    for i in raftconfig.ADDRESS_BY_IDENTIFIER:
        threading.Thread(target=self.deliver, args=(i,)).start()

    print("start.")
```

One thread listens for incoming connections. One thread per target server handles outgoing messages.

The **listener** accepts connections and spawns per-connection handlers:

```python
def listen(self) -> None:
    while True:
        client, address = self.socket.accept()
        threading.Thread(target=self._listen, args=(client,)).start()

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

Messages are length-prefixed: 4 bytes for the length, then the message bytes. This handles message framing over TCP's stream interface.

The **deliverers** send messages to their target servers:

```python
def deliver(self, identifier: int) -> None:
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

Each deliverer maintains a persistent connection to its target. If sending fails, the connection is dropped and reconnected on the next message.

## Best-Effort Delivery

Note the comment in `deliver`:

> The delivery is best-efforts, in which the message is discarded if the remote server is not operational.

If a send fails, the message is lost. No retries at the network level. This is fine because Raft handles message loss through its own mechanisms:

- Lost heartbeats trigger election timeouts
- Lost AppendEntries get resent on the next heartbeat
- Lost votes get resent when the candidate times out

The network layer doesn't need reliability—Raft provides it at the application layer.

## The Incoming and Outgoing Queues

Messages flow through thread-safe queues:

- **incoming**: One shared queue. All received messages go here. The main loop reads from it.
- **outgoing**: One queue per target server. When `send()` is called, the message goes into the appropriate queue. The deliverer thread reads from it.

Python's `queue.Queue` handles synchronization. Multiple threads can safely put/get without explicit locking.

## The RaftServer Orchestrator

`RaftServer` combines the pieces:

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

Three components:
- **state**: The Raft state machine from Chapter 5
- **node**: The network abstraction
- **timer**: For election timeouts

The `run` method starts everything:

```python
def run(self):
    self.node.start()    # Start network threads
    self.timer.start()   # Start timeout timer
    self.respond()       # Enter main loop

    print(self.color() + "end.")
    os._exit(0)
```

## The Response Loop

The main loop in `respond` processes messages forever:

```python
def respond(self) -> None:
    while True:
        payload = self.node.receive()  # Block until message arrives

        try:
            request = raftmessage.decode_message(payload)
            print(
                self.color() + f"\n{request.source} > {request.target} {payload}",
                end="",
            )

            # Check if this message should prevent timeout transition
            if (self.state.role, type(request)) in [
                (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
                (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
                (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
            ]:
                self.reset = False

            if not isinstance(request, raftmessage.Text):
                print(self.color() + f"\n{request.target} > ", end="")

            response = self.state.handle_message(request)
            self.send(response)

        except Exception as e:
            print(self.color() + f"Exception: {e}")
```

The flow:
1. Block waiting for a message
2. Decode it
3. Check if it should suppress timeout transitions
4. Pass it to the state machine
5. Send any response messages

The colored output helps debugging. Prompts show green for leader, yellow for candidate, red for follower.

## Timer Mechanics

Timeouts drive elections. Python's `threading.Timer` runs a callback after a delay:

```python
self.timer: threading.Timer = threading.Timer(TIMEOUT, self.timeout)
```

The `timeout` method handles what happens when the timer fires:

```python
def timeout(self) -> None:
    # Add random jitter for followers
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)

    # Only act if no relevant messages received
    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))

    self.cycle()
```

The timeout creates a message and puts it in the incoming queue—so it gets processed by the same loop as network messages. This keeps the message handling uniform.

## The Reset Flag Pattern

The `reset` flag prevents redundant state changes. The pattern:

1. At cycle start: `reset = True`
2. When receiving certain messages: `reset = False`
3. At timeout: only act if `reset` is still `True`

Which messages suppress the timeout?

```python
if (self.state.role, type(request)) in [
    (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
    (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
    (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
]:
    self.reset = False
```

- Followers receiving heartbeats shouldn't time out and become candidates
- Followers receiving vote requests have an active election happening
- Candidates receiving vote responses are still counting votes

Without this flag, a message arriving just before the timeout could cause both the message handler and the timeout handler to change state.

## The Cycle Method

After each timeout (whether it triggered action or not), `cycle` resets the timer:

```python
def cycle(self) -> None:
    timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

    self.timer.cancel()
    self.timer = threading.Timer(timeout, self.timeout)
    self.timer.start()

    self.reset = True
```

Note the different timeouts:
- Leaders: 3 seconds (TIMEOUT)
- Followers/Candidates: 6 seconds (2 * TIMEOUT)

Leaders need to send heartbeats frequently. Followers can wait longer before declaring the leader dead.

## Configuration

The cluster configuration lives in `raftconfig.py`:

```python
ADDRESS_BY_IDENTIFIER: Dict[int, Tuple[str, int]] = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

Simple: server ID maps to (host, port). All three servers run on localhost with different ports.

To run on multiple machines, you'd change the hostnames. To change cluster size, add or remove entries. There's no dynamic membership—you'd need to restart all servers with the new configuration.

## The Client

`RaftClient` lets you interact with the cluster:

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
                self.send([
                    raftmessage.Text(self.identifier, target, prompt)
                    for target in raftconfig.ADDRESS_BY_IDENTIFIER
                ])
                continue

            target, command = int(prompt[0]), prompt[2:]
            messages: List[raftmessage.Message] = []

            if command.startswith("append"):
                for item in command.replace("append ", "").split():
                    messages.append(
                        raftmessage.ClientLogAppend(self.identifier, target, item)
                    )
```

Commands:
- `self`: Query all servers' state (sends `Text` message)
- `1 append a b c`: Send three `ClientLogAppend` messages to server 1

The client must know which server is leader. If you send `append` to a follower, it will fail (the follower raises an exception). In a production system, the client would retry with different servers or the follower would redirect to the leader.

## What This Implementation Omits

Several features you'd need for production:

**Persistence**: All state is in memory. Restart a server and it loses everything. Production systems write `currentTerm`, `votedFor`, and `log` to disk before responding to any RPC.

**Log compaction**: The log grows forever. Production systems snapshot the state machine periodically and truncate old log entries.

**Dynamic membership**: The cluster size is fixed at startup. Production systems support adding/removing servers at runtime (Raft's joint consensus protocol).

**Client sessions**: The client has no way to know if a command succeeded. Production systems track client sessions to ensure exactly-once semantics.

**Read consistency**: Reading state requires going through the leader (or using read-only RPCs with lease checks). This implementation doesn't expose reads.

These omissions are deliberate. Each feature adds complexity that would obscure the core algorithm. This implementation focuses on making Raft understandable, not production-ready.

## Tracing a Message

Let's trace a heartbeat through the system:

1. Leader's timer fires, `timeout` is called
2. `change_state_on_timeout` returns an `UpdateFollowers` message
3. The message is put in `incoming` queue
4. `respond` loop reads it, decodes it
5. `handle_message` dispatches to `handle_leader_heartbeat`
6. Handler creates `AppendEntryRequest` messages for each follower
7. `send` encodes each message and puts it in the appropriate `outgoing` queue
8. Deliverer thread reads from queue, sends over socket
9. Follower's listener thread receives, puts in `incoming` queue
10. Follower's `respond` loop processes, responds
11. Response travels back the same way
12. Leader's `handle_append_entries_response` updates `matchIndex`

All that happens in a few hundred lines of code.

## Conclusion

The runtime layer is intentionally thin. `RaftNode` provides send/receive. `RaftServer` provides the event loop. Everything interesting happens in `RaftState`.

This separation makes the system testable: you can verify the algorithm by feeding messages directly to `RaftState`, without networks or timers. It makes the code readable: network concerns in one place, algorithm in another.

The runtime is also where the implementation cuts corners. Best-effort delivery, no persistence, fixed membership. These choices keep the code simple. A production system would need more robust networking, disk storage, and membership management—but the core algorithm would remain the same.

That's the architectural lesson: separate the algorithm from the infrastructure. The algorithm is hard to get right; keep it isolated where you can test it. The infrastructure is well-understood; use standard patterns. The boundary between them should be clean.

You now understand a complete Raft implementation: log structure, messages, roles, state machine, replication, elections, and runtime. The code is real and runnable. The patterns are applicable to any distributed system you build.
