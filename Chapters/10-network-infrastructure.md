# Chapter 10: Network Infrastructure

## Introduction

This chapter covers the network layer that lets nodes communicate. The `RaftNode` class in `raftnode.py` wraps sockets, threads, and queues to provide a simple send/receive interface. Understanding this layer shows how the pure protocol logic connects to real network I/O.

## 10.1 The RaftNode Class

`RaftNode` provides a minimal interface for network communication:

```python
@dataclasses.dataclass
class RaftNode:
    identifier: int

    def __post_init__(self) -> None:
        self.socket: socket.socket = initialize_socket(self.identifier)
        self.incoming: queue.Queue = queue.Queue()
        self.outgoing: Dict[int, queue.Queue] = {
            identifier: queue.Queue()
            for identifier in raftconfig.ADDRESS_BY_IDENTIFIER
        }
```

Three components:
- **`socket`**: TCP socket for accepting incoming connections
- **`incoming`**: Queue of received messages (for the main thread to consume)
- **`outgoing`**: Per-peer queues of messages to send

The main thread only needs two operations:
- `send(identifier, message)`: Queue a message for delivery to a peer
- `receive()`: Block until a message arrives in the incoming queue

## 10.2 Socket Initialization

Each node listens on a configured address:

```python
def initialize_socket(identifier: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.bind(raftconfig.ADDRESS_BY_IDENTIFIER[identifier])
    sock.listen()

    return sock
```

Key points:
- `SO_REUSEADDR` allows quick restarts (reuse the port immediately after shutdown)
- Address comes from `raftconfig.ADDRESS_BY_IDENTIFIER` mapping
- `listen()` marks the socket as accepting connections

## 10.3 The Incoming Queue

Background threads handle incoming connections:

```python
def listen(self) -> None:
    while True:
        client, address = self.socket.accept()
        threading.Thread(target=self._listen, args=(client,)).start()
```

Each accepted connection spawns a new thread:

```python
def _listen(self, client: socket.socket) -> None:
    while True:
        length = int.from_bytes(client.recv(4), byteorder="big")

        if length == 0:
            break

        message = client.recv(length).decode("ascii")
        self.incoming.put(message)
```

The main thread blocks on `self.incoming.get()`, receiving messages from any peer through this single queue.

## 10.4 Message Framing

TCP is a stream protocol—it doesn't preserve message boundaries. The implementation uses length-prefixing to frame messages:

**Sending:**
```python
def _deliver(
    self, sock: Optional[socket.socket], address: Tuple[str, int], message: str
) -> Optional[socket.socket]:
    try:
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(address)

        message_bytes = message.encode("ascii")
        sock.sendall(len(message_bytes).to_bytes(4, byteorder="big"))
        sock.sendall(message_bytes)

        return sock

    except (socket.error, BrokenPipeError, ConnectionRefusedError):
        return None
```

First 4 bytes: message length (big-endian). Remaining bytes: message content.

**Receiving:**
```python
length = int.from_bytes(client.recv(4), byteorder="big")
message = client.recv(length).decode("ascii")
```

Read 4 bytes for length, then read exactly that many bytes for the message.

## 10.5 Outgoing Queues and Delivery

Each peer has its own outgoing queue and delivery thread:

```python
def send(self, identifier: int, message: str) -> None:
    self.outgoing[identifier].put(message)


def deliver(self, identifier: int) -> None:
    sock = None
    address = raftconfig.ADDRESS_BY_IDENTIFIER[identifier]

    while True:
        message = self.outgoing[identifier].get()
        sock = self._deliver(sock, address, message)
```

Why per-peer queues?
- **Independence**: A slow peer doesn't block messages to other peers
- **Connection reuse**: Each delivery thread maintains its own connection
- **Simple ordering**: Messages to the same peer are delivered in queue order

## 10.6 Best-Effort Delivery

Delivery is best-effort. If a connection fails, the message is silently dropped:

```python
except (socket.error, BrokenPipeError, ConnectionRefusedError):
    return None
```

This matches Raft's network model: messages can be lost, delayed, or reordered. The protocol handles this through:
- Heartbeat timeouts (detect when leader is unreachable)
- Retry logic (resend failed `AppendEntryRequest`)
- Idempotent handlers (duplicate messages don't corrupt state)

A production implementation might add message acknowledgments or persistent queues, but for learning, explicit loss is clearer than hidden complexity.

## 10.7 Connection Reuse

The `_deliver` method reuses connections when possible:

```python
def _deliver(self, sock, address, message):
    try:
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(address)

        # ... send message ...

        return sock  # Return socket for reuse

    except ...:
        return None  # Connection failed, will create new one next time
```

Benefits:
- Leaders send frequent heartbeats—connection reuse reduces overhead
- Avoids TCP handshake for every message
- Connection failures are detected on next send attempt

## 10.8 Starting the Node

`start()` launches all background threads:

```python
def start(self) -> None:
    threading.Thread(target=self.listen, args=()).start()

    for i in raftconfig.ADDRESS_BY_IDENTIFIER:
        threading.Thread(target=self.deliver, args=(i,)).start()
```

After `start()`:
- One thread accepts incoming connections (spawning more threads per connection)
- One thread per peer delivers outgoing messages
- The main thread can call `receive()` and `send()` without blocking on I/O

## 10.9 Thread Safety

The queues provide thread safety:
- `queue.Queue` is thread-safe by design
- Multiple listener threads can safely `put()` to `incoming`
- The main thread safely `get()`s from `incoming`
- Only one thread `get()`s from each `outgoing[i]` queue

No additional locking is needed.

## 10.10 Receive and Send

The public interface is simple:

```python
def receive(self) -> str:
    return self.incoming.get()


def send(self, identifier: int, message: str) -> None:
    self.outgoing[identifier].put(message)
```

`receive()` blocks until a message is available. `send()` is non-blocking (just enqueues).

## Conclusion

`RaftNode` provides the network substrate for Raft communication. Background threads handle listening (one per connection) and delivery (one per peer), placing incoming messages in a queue for the main protocol loop. Delivery is best-effort with connection reuse. The layer is intentionally simple—all reliability is handled by the protocol above. This separation means you can test the protocol without any networking, then add the network layer for actual deployment.
