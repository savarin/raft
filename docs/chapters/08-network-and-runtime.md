# Chapter 8: Network and Runtime

## What This Chapter Covers

The previous chapters explained the Raft algorithm as pure state machine logic. This chapter shows how that logic runs in practice: `RaftNode` for network communication, `RaftServer` for orchestration, and timers for driving elections. You'll see how the clean abstractions compose into a working distributed system.

This chapter completes the picture. After reading it, you can trace a message from one server to another, watch state change in response, and understand how timeouts trigger elections. You'll also understand the intentional limitations—what this implementation omits and why.

## Sections

### The RaftNode Abstraction

`RaftNode` wraps sockets and queues. `send(identifier, message)` is non-blocking—it queues the message for delivery. `receive()` is blocking—it waits for a message to arrive. Why this interface: decouples the state machine from network details.

### Socket Management

`initialize_socket` binds to the configured address. Background threads for listening (one per incoming connection) and delivering (one per outgoing target). Best-effort delivery: if a send fails, the message is lost. Why this is okay—Raft tolerates message loss.

### The Incoming and Outgoing Queues

Messages flow through queues. Incoming queue: one shared queue, all received messages. Outgoing queues: one per target server, messages waiting to be sent. Thread-safe access via Python's `queue.Queue`.

### The RaftServer Orchestrator

`RaftServer` combines `RaftState`, `RaftNode`, and a timer. The `run` method: start network threads, start timer, enter the response loop. Simple composition of the components built in earlier chapters.

### The Response Loop

`respond` runs forever: receive message, decode, dispatch to state machine, encode responses, send. The coloring logic that shows role visually. Exception handling that keeps the server running through errors.

### Timer Mechanics

`threading.Timer` for timeouts. Different timeouts for different roles: leaders check quickly (3 seconds), followers wait longer (6 seconds plus jitter). The `cycle` method resets the timer after each period.

### The Reset Flag Pattern

The `reset` flag prevents redundant state changes. Set to `True` at cycle start. Set to `False` when receiving heartbeats or votes. Only trigger state change on timeout if still `True`. This handles the case where a heartbeat arrives just before timeout.

### Configuration

`raftconfig` holds server addresses. A simple dictionary mapping identifiers to (host, port) tuples. How to change cluster membership (not supported dynamically, but easy to modify).

### The Client

`raftclient.py` for sending commands. The `append` command to add log entries. The `self` command to query server state. Why the client must know the leader—or try each server.

### What This Implementation Omits

No persistence—state is lost on restart. No dynamic membership changes. No log compaction or snapshots. These are features for production systems; this implementation focuses on the core algorithm.

## Conclusion

The runtime layer is intentionally thin. `RaftNode` provides send/receive. `RaftServer` provides the event loop. Everything interesting happens in `RaftState`. This separation makes the system testable—you can test the algorithm without starting threads or opening sockets. It also makes the code readable: network concerns in one place, algorithm in another. That's the architectural lesson of this implementation.
