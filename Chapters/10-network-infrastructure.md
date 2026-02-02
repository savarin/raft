# Chapter 10: Network Infrastructure

## Introduction

This chapter covers the network layer that lets nodes communicate. The `RaftNode` class in `raftnode.py` wraps sockets, threads, and queues to provide a simple send/receive interface. Understanding this layer shows how the pure protocol logic connects to real network I/O.

## Sections

### 10.1 The RaftNode Class

`RaftNode` provides two operations:
- `send(identifier, message)`: Queue a message for delivery
- `receive()`: Block until a message arrives

```python
@dataclasses.dataclass
class RaftNode:
    identifier: int

    def __post_init__(self) -> None:
        self.socket: socket.socket = initialize_socket(self.identifier)
        self.incoming: queue.Queue = queue.Queue()
        self.outgoing: Dict[int, queue.Queue] = {...}
```

### 10.2 Socket Initialization

Each node listens on a configured port:

```python
def initialize_socket(identifier: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.bind(address)
    sock.listen()
    return sock
```

Address mapping comes from `raftconfig.ADDRESS_BY_IDENTIFIER`.

### 10.3 The Incoming Queue

The `listen` method runs in a background thread, accepting connections and reading messages:

```python
def listen(self) -> None:
    while True:
        client, address = self.socket.accept()
        threading.Thread(target=self._listen, args=(client,)).start()
```

Messages are placed in `self.incoming` for the main thread to consume.

### 10.4 Message Framing

Messages are length-prefixed:
1. Send: 4 bytes (big-endian length) + message bytes
2. Receive: Read 4 bytes for length, then read that many bytes

```python
def _listen(self, client: socket.socket) -> None:
    while True:
        length = int.from_bytes(client.recv(4), byteorder="big")
        message = client.recv(length).decode("ascii")
        self.incoming.put(message)
```

### 10.5 Outgoing Queues and Delivery

Each peer has its own outgoing queue. Delivery threads process these queues:

```python
def deliver(self, identifier: int) -> None:
    sock = None
    address = raftconfig.ADDRESS_BY_IDENTIFIER[identifier]

    while True:
        message = self.outgoing[identifier].get()
        sock = self._deliver(sock, address, message)
```

### 10.6 Best-Effort Delivery

Delivery is best-effort: if a peer is down, the message is lost. This matches Raft's assumption of unreliable networks. The protocol handles message loss through retries and timeouts.

### 10.7 Connection Reuse

`_deliver` reuses connections when possible:
- If `sock` is None, create new connection
- If send fails, set `sock = None` for next attempt
- Persistent connections reduce overhead for frequent heartbeats

### 10.8 Starting the Node

`start()` launches all background threads:

```python
def start(self) -> None:
    threading.Thread(target=self.listen, args=()).start()

    for i in raftconfig.ADDRESS_BY_IDENTIFIER:
        threading.Thread(target=self.deliver, args=(i,)).start()
```

## Conclusion

`RaftNode` provides the network substrate for Raft communication. Background threads handle listening and delivery, placing incoming messages in a queue for the main protocol loop. Delivery is best-effort with connection reuse. This layer is intentionally simple—the protocol above handles unreliability.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- `RaftNode` class
- `send()` and `receive()` interface
- Socket initialization and binding
- Length-prefixed message framing
- Incoming queue and listener thread
- Outgoing queues and delivery threads
- Best-effort delivery semantics
- Connection reuse

**Back-references**:
- Chapter 2 placed `raftnode.py` in the network layer
- Chapter 7 showed message encoding that produces the bytes sent here

**Forward dependencies**:
- Chapter 11 uses `RaftNode` inside `RaftServer`
- Chapter 12 shows the client using `RaftNode`
