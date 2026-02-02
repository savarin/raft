# Chapter 12: Running the Cluster

## Introduction

This chapter covers how to run and interact with the Raft cluster. You start three server processes, each listening on its configured port, and use a client to send commands. Watching the cluster elect a leader, replicate entries, and handle failures brings the algorithm to life.

## Sections

### 12.1 Configuration

`raftconfig.py` defines the cluster topology:

```python
ADDRESS_BY_IDENTIFIER: Dict[int, Tuple[str, int]] = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

Three nodes, all on localhost with different ports. Modify this to run on multiple machines.

### 12.2 Starting Servers

Each server runs in its own terminal:

```shell
# Terminal 1
python src/raftserver.py 1

# Terminal 2
python src/raftserver.py 2

# Terminal 3
python src/raftserver.py 3
```

The prompt shows the server identifier. Prompt color indicates role:
- Red: Follower
- Yellow: Candidate
- Green: Leader

### 12.3 Observing Leader Election

When servers start:
1. All begin as followers (red prompt)
2. After timeout, one becomes candidate (yellow)
3. If it wins majority, it becomes leader (green)
4. Others remain followers, receiving heartbeats

### 12.4 The Raft Client

Start the client in a fourth terminal:

```shell
python src/raftclient.py 0
```

The client connects to the cluster but isn't part of consensus.

### 12.5 Appending Entries

Send entries to the leader:

```shell
0 > 1 append a b c
```

Format: `<server_id> append <entry1> <entry2> ...`

The leader appends to its log and replicates to followers.

### 12.6 Inspecting State

The `self` command shows all servers' state:

```shell
0 > self
```

Each server prints its current state: role, term, log, commit index, etc.

### 12.7 Simulating Failures

Kill a server (Ctrl+C) to simulate failure:
- If you kill the leader, remaining servers elect a new one
- If you kill a follower, the cluster continues with reduced redundancy
- If you kill two servers, the remaining one can't achieve majority

Restart the server to see log reconciliation in action.

### 12.8 Observing Log Reconciliation

After a partition heals:
1. Leader sends `AppendEntryRequest` with current log state
2. Rejoining follower may reject (log mismatch)
3. Leader backs up `nextIndex` and retries
4. Eventually logs converge

Watch the message flow in server output to see this happening.

### 12.9 The Client Implementation

`RaftClient` is simpler than `RaftServer`:

```python
@dataclasses.dataclass
class RaftClient:
    identifier: int

    def __post_init__(self) -> None:
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)
```

It uses the same `RaftNode` for network I/O but doesn't participate in consensus—no state, no handlers, just message sending.

### 12.10 Limitations of This Implementation

This is a learning implementation, not production-ready:
- No persistence (state lost on restart)
- No log compaction (unbounded memory)
- No cluster membership changes
- No client request routing (must know the leader)
- Hardcoded three-node cluster

## Conclusion

Running the cluster demonstrates Raft in action: leader election, log replication, and failure handling. Start three servers, connect a client, append entries, and observe the message flow. Kill servers to see elections and log reconciliation. This hands-on experimentation builds intuition that reading code alone cannot provide.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Cluster configuration (`raftconfig.py`)
- Starting servers and client
- Prompt color coding for roles
- `append` command for entries
- `self` command for state inspection
- Simulating failures and observing recovery
- Client implementation
- Implementation limitations

**Back-references**:
- Chapter 8's election process visible in role color changes
- Chapter 9's log reconciliation observable through message flow
- Chapter 10's `RaftNode` used by client
- Chapter 11's `RaftServer` being run here

**Forward dependencies**: None (final chapter)
