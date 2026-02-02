# Chapter 11: The Raft Server

## Introduction

This chapter covers how `RaftServer` combines state, network, and timer into a running Raft node. The server is the integration point: it receives messages from the network, passes them to `RaftState` handlers, sends responses, and manages timeouts that trigger elections and heartbeats.

## Sections

### 11.1 The RaftServer Class

`RaftServer` composes the pieces:

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

### 11.2 The Main Loop

`respond()` is the event loop:

```python
def respond(self) -> None:
    while True:
        payload = self.node.receive()
        request = raftmessage.decode_message(payload)
        response = self.state.handle_message(request)
        self.send(response)
```

1. Block waiting for a message
2. Decode the message
3. Pass to state handler
4. Send any response messages

### 11.3 Timeout Management

Timeouts trigger elections (followers) and heartbeats (leaders):

```python
def timeout(self) -> None:
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)  # Randomize

    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))

    self.cycle()
```

The timeout handler puts a message in the incoming queue, letting it flow through the normal handler path.

### 11.4 The Reset Flag

The `reset` flag prevents spurious timeouts:

```python
if (self.state.role, type(request)) in [
    (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
    (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
    (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
]:
    self.reset = False
```

If a follower receives a heartbeat or vote request, don't trigger election on next timeout. The flag resets at the start of each timer cycle.

### 11.5 Role-Based Timeout Duration

Leaders use shorter timeouts (heartbeat interval), followers use longer timeouts (election timeout):

```python
def cycle(self) -> None:
    timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

    self.timer.cancel()
    self.timer = threading.Timer(timeout, self.timeout)
    self.timer.start()
```

### 11.6 Randomized Election Timeout

The random sleep before follower elections prevents split votes:

```python
if self.state.role == raftrole.Role.FOLLOWER:
    time.sleep(random.random() * TIMEOUT)
```

Different followers wake up at different times, so one usually wins before others start.

### 11.7 Leader Step-Down

If a leader receives no `AppendEntryResponse` between heartbeats, it may be partitioned. The `has_followers` flag tracks this:

```python
# In change_state_on_timeout:
if not state.has_followers:
    return raftmessage.RoleChange(..., LEADER, FOLLOWER)

state.has_followers = False  # Reset for next cycle
```

### 11.8 Starting the Server

`run()` starts all components:

```python
def run(self):
    self.node.start()   # Start network threads
    self.timer.start()  # Start timeout timer
    self.respond()      # Enter main loop
```

## Conclusion

`RaftServer` integrates state, network, and timer into a running node. The main loop receives messages, dispatches to handlers, and sends responses. Timeouts trigger elections and heartbeats by injecting messages into the incoming queue. The reset flag and role-based timeout durations coordinate the timing behavior.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- `RaftServer` class composition
- Main event loop (`respond`)
- Timeout handling and injection into message queue
- Reset flag for timeout suppression
- Role-based timeout durations
- Randomized election timeout
- Leader step-down on isolation (`has_followers`)

**Back-references**:
- Chapter 6 introduced `has_followers` state attribute
- Chapter 8 mentioned randomized timeout for split vote prevention
- Chapter 10 introduced `RaftNode` used here

**Forward dependencies**:
- Chapter 12 shows how to run servers and interact with them
