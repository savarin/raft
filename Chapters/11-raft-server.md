# Chapter 11: The Raft Server

## Introduction

This chapter covers how `RaftServer` combines state, network, and timer into a running Raft node. The server is the integration point: it receives messages from the network, passes them to `RaftState` handlers, sends responses, and manages timeouts that trigger elections and heartbeats.

## 11.1 The RaftServer Class

`RaftServer` composes the pieces we've seen in previous chapters:

```python
TIMEOUT = 1


@dataclasses.dataclass
class RaftServer:
    identifier: int

    def __post_init__(self) -> None:
        self.state: raftstate.RaftState = raftstate.RaftState(self.identifier)
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)
        self.timer: threading.Timer = threading.Timer(TIMEOUT, self.timeout)
        self.reset: bool = True
```

Four components:
- **`state`**: The `RaftState` from Chapter 6 (log, role, handlers)
- **`node`**: The `RaftNode` from Chapter 10 (network I/O)
- **`timer`**: Threading timer for election/heartbeat timeouts
- **`reset`**: Flag controlling timeout behavior

## 11.2 The Main Loop

`respond()` is the event loop that processes messages:

```python
def respond(self) -> None:
    while True:
        payload = self.node.receive()
        request = raftmessage.decode_message(payload)

        if (self.state.role, type(request)) in [
            (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
            (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
            (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
        ]:
            self.reset = False

        response = self.state.handle_message(request)
        self.send(response)
        self.cycle()
```

The loop:
1. Block waiting for a message from the network
2. Decode the message from Bencode
3. Update the `reset` flag if this message should suppress timeout
4. Pass to `handle_message` and get response messages
5. Send responses
6. Reset the timer

## 11.3 Timeout Management

The timer triggers elections (for followers) and heartbeats (for leaders):

```python
def timeout(self) -> None:
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)

    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))

    self.cycle()
```

Key design: the timeout handler doesn't call `handle_message` directly. Instead, it puts a message in the incoming queue:

```python
self.node.incoming.put(raftmessage.encode_message(message))
```

This ensures all state changes flow through the same code path—the main loop's `handle_message` call. Benefits:
- Consistent logging and debugging
- No race conditions between timeout and network messages
- Testable: timeouts are just messages

## 11.4 The Reset Flag

The `reset` flag prevents spurious timeouts:

```python
if (self.state.role, type(request)) in [
    (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
    (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
    (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
]:
    self.reset = False
```

When a follower receives:
- An `AppendEntryRequest` (heartbeat from leader)
- A `RequestVoteRequest` (candidate seeking votes)

...it sets `reset = False`. When the timer fires, if `reset` is `False`, no timeout message is injected:

```python
def timeout(self) -> None:
    # ...
    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(...)

    self.cycle()  # Reset timer for next cycle
```

This prevents a follower from starting an election immediately after receiving a valid heartbeat.

The `cycle()` method resets the flag for the next interval:

```python
def cycle(self) -> None:
    self.reset = True  # Reset for next cycle
    # ... restart timer ...
```

## 11.5 Role-Based Timeout Duration

Leaders and followers use different timeout durations:

```python
def cycle(self) -> None:
    self.reset = True
    timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

    self.timer.cancel()
    self.timer = threading.Timer(timeout, self.timeout)
    self.timer.start()
```

- **Leader**: `TIMEOUT` (1 second) — sends heartbeats frequently
- **Follower/Candidate**: `2 * TIMEOUT` (2 seconds) — gives time for heartbeats to arrive

The leader's shorter timeout ensures heartbeats are sent before followers time out.

## 11.6 Randomized Election Timeout

To prevent split votes, followers add random delay before starting elections:

```python
def timeout(self) -> None:
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)
```

If three followers all have their timers expire simultaneously, this random delay staggers them. The first one to wake up starts an election and (usually) wins before others start.

Without this randomization, split votes could repeat indefinitely: all candidates request votes at the same time, each gets some votes, none gets majority, all time out, repeat.

## 11.7 Leader Step-Down

A leader must step down if it becomes isolated (no followers responding):

```python
def change_state_on_timeout(state: RaftState) -> raftmessage.Message:
    match state.role:
        case raftrole.Role.LEADER:
            assert state.has_followers is not None

            if not state.has_followers:
                return raftmessage.RoleChange(
                    state.identifier,
                    state.identifier,
                    raftrole.Role.LEADER,
                    raftrole.Role.FOLLOWER,
                )

            state.has_followers = False

            return raftmessage.UpdateFollowers(
                state.identifier,
                state.identifier,
                state.create_followers_list(),
            )
```

The logic:
1. If `has_followers` is `False`, no responses since last heartbeat → step down
2. Otherwise, reset `has_followers` to `False` and send new heartbeat
3. If responses arrive before next timeout, `has_followers` becomes `True`

This prevents a partitioned leader from accepting writes that can't be replicated.

## 11.8 Sending Responses

The `send` method handles response messages:

```python
def send(self, response: List[raftmessage.Message]) -> None:
    for message in response:
        if message.target == self.identifier:
            self.node.incoming.put(raftmessage.encode_message(message))
        else:
            self.node.send(message.target, raftmessage.encode_message(message))
```

Two cases:
- **Self-targeted messages**: Go back to the incoming queue (internal events like `UpdateFollowers` after becoming leader)
- **External messages**: Sent over the network via `RaftNode`

## 11.9 Starting the Server

`run()` starts all components:

```python
def run(self):
    self.node.start()   # Start network threads
    self.timer.start()  # Start timeout timer
    self.respond()      # Enter main loop (blocks forever)
```

The main script:

```python
if __name__ == "__main__":
    identifier = int(sys.argv[1])
    raftServer = RaftServer(identifier)
    raftServer.run()
```

## 11.10 The Prompt

The server displays a colored prompt indicating its role:

```python
RED = "\033[1;31m"    # Follower
YELLOW = "\033[1;33m" # Candidate
GREEN = "\033[1;32m"  # Leader
DEFAULT = "\033[0m"

def prompt(state: raftstate.RaftState):
    match state.role:
        case raftrole.Role.FOLLOWER:
            color = RED
        case raftrole.Role.CANDIDATE:
            color = YELLOW
        case raftrole.Role.LEADER:
            color = GREEN

    print(f"{color}{str(state.identifier)} {str(state.role.value)}{DEFAULT} > ", end="")
```

This visual feedback helps when observing the cluster.

## Conclusion

`RaftServer` integrates state, network, and timer into a running node. The main loop receives messages, dispatches to handlers, and sends responses. Timeouts trigger elections and heartbeats by injecting messages into the incoming queue, ensuring all state changes flow through `handle_message`. The reset flag prevents spurious elections after heartbeats. Role-based timeout durations ensure heartbeats are sent before followers time out. Randomized election delays prevent split votes. Leader isolation detection forces step-down when partitioned.
