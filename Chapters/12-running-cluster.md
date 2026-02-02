# Chapter 12: Running the Cluster

## Introduction

This chapter covers how to run and interact with the Raft cluster. You start three server processes, each listening on its configured port, and use a client to send commands. Watching the cluster elect a leader, replicate entries, and handle failures brings the algorithm to life.

## 12.1 Configuration

The cluster topology is defined in `raftconfig.py`:

```python
from typing import Dict, Tuple

ADDRESS_BY_IDENTIFIER: Dict[int, Tuple[str, int]] = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

Each node has:
- An integer identifier (1, 2, or 3)
- A host and port tuple

For a single-machine demo, all nodes use "localhost" with different ports. To run on multiple machines, change the hostnames.

## 12.2 Starting Servers

Open three terminal windows and start each server:

```shell
# Terminal 1
cd /path/to/raft
python src/raftserver.py 1
```

```shell
# Terminal 2
python src/raftserver.py 2
```

```shell
# Terminal 3
python src/raftserver.py 3
```

Each server displays a prompt with its identifier and role:
- Red prompt: Follower
- Yellow prompt: Candidate
- Green prompt: Leader

## 12.3 Observing Leader Election

When servers start, you'll see election unfold:

1. **Initial state**: All three servers start as followers (red prompts)

2. **Timeout**: After the election timeout (2 seconds), one server times out. Due to randomized delays, one usually wins the race

3. **Candidate phase**: The first server to time out becomes a candidate (yellow prompt), increments its term, and sends `RequestVoteRequest` to others

4. **Voting**: Other servers receive the vote request and grant their vote (they haven't voted yet this term)

5. **Election victory**: The candidate receives two votes (including its own), reaches majority, and becomes leader (green prompt)

6. **Heartbeats**: The leader immediately sends `AppendEntryRequest` heartbeats. Other servers receive them and remain followers

The entire process takes a few seconds.

## 12.4 The Raft Client

Start the client in a fourth terminal:

```shell
python src/raftclient.py 0
```

The client uses identifier 0 (not part of the cluster's consensus quorum). It can send messages but doesn't vote or replicate logs.

```python
@dataclasses.dataclass
class RaftClient:
    identifier: int

    def __post_init__(self) -> None:
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)

    def run(self):
        self.node.start()

        while True:
            instructions = input(f"{self.identifier} > ").split(" ")
            # Parse and send messages...
```

## 12.5 Appending Entries

Send entries to the leader using the `append` command:

```shell
0 > 1 append a b c
```

Command format: `<server_id> append <entry1> <entry2> ...`

What happens:
1. Client sends `ClientLogAppend` message to server 1
2. If server 1 is leader, it appends entries to its log
3. On next heartbeat, leader replicates entries to followers
4. When majority acknowledges, entries are committed

Check that entries were replicated using `self`:

```shell
0 > self
```

## 12.6 Inspecting State

The `self` command asks all servers to print their state:

```shell
0 > self
```

Each server responds with:
- Role (FOLLOWER/CANDIDATE/LEADER)
- Current term
- Log contents
- Commit index
- Other state attributes

Example output on a server:

```
RaftState(identifier=1)
role: LEADER
current_term: 1
log: [LogEntry(1, 'a'), LogEntry(1, 'b'), LogEntry(1, 'c')]
commit_index: 2
next_index: {1: 3, 2: 3, 3: 3}
match_index: {1: 2, 2: 2, 3: 2}
```

## 12.7 Simulating Failures

Kill a server with Ctrl+C to simulate failure:

**Killing the leader:**
1. Press Ctrl+C on the leader's terminal
2. Followers stop receiving heartbeats
3. After election timeout, one becomes candidate
4. It wins election and becomes new leader
5. Cluster continues operating (with reduced redundancy)

**Killing a follower:**
1. Press Ctrl+C on a follower's terminal
2. Leader continues sending heartbeats (which fail silently)
3. Leader still has one other follower
4. Cluster continues operating (2 of 3 nodes is still majority)

**Killing two servers:**
1. Kill two servers, leaving only one
2. The remaining server can't achieve majority
3. If it's the leader, it will step down after detecting isolation
4. No new leader can be elected (no majority possible)
5. Restart one server to restore quorum

## 12.8 Observing Log Reconciliation

To see log reconciliation:

1. Append some entries while all three servers are running
2. Kill a follower (server 2)
3. Append more entries to the leader
4. Restart server 2

What happens:
1. Server 2 starts with its old log state
2. Leader sends `AppendEntryRequest` with current log state
3. Server 2 rejects (log mismatch at `previous_index`)
4. Leader decrements `next_index[2]` and retries
5. After a few retries, they find the matching point
6. Server 2 receives and appends the missing entries
7. Logs converge

Watch the console output to see the retry sequence.

## 12.9 The Client Implementation

`RaftClient` is simpler than `RaftServer`:

```python
@dataclasses.dataclass
class RaftClient:
    identifier: int

    def __post_init__(self) -> None:
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)

    def run(self):
        self.node.start()

        while True:
            instructions = input(f"{self.identifier} > ").split(" ")

            if len(instructions) == 1:
                target = int(instructions[0])
                message = raftmessage.Text(self.identifier, target, "self")
            else:
                target = int(instructions[0])
                action = instructions[1]
                items = instructions[2:]

                if action == "append":
                    for item in items:
                        message = raftmessage.ClientLogAppend(
                            self.identifier, target, item
                        )
                        self.node.send(
                            target, raftmessage.encode_message(message)
                        )
                    continue
```

The client:
- Uses `RaftNode` for network I/O (same as servers)
- Doesn't maintain `RaftState` (no protocol participation)
- Just sends messages and observes responses

## 12.10 Limitations of This Implementation

This is a learning implementation, not production-ready:

**No persistence**: All state is in memory. Restarting a server loses its log, term, and voted-for state. A production system would write these to disk.

**No log compaction**: The log grows unboundedly. Real systems use snapshotting to truncate old entries.

**No cluster membership changes**: The three-node configuration is hardcoded. The Raft paper's Section 6 describes joint consensus for safe membership changes.

**No client request routing**: Clients must know which server is leader. A real system would redirect or proxy requests.

**No client request deduplication**: If a client retries a request, it might be applied twice. Production systems track client request IDs.

**Fixed cluster size**: The majority calculation assumes three nodes. Changing cluster size requires code changes.

**No read optimization**: All reads go through the leader's log. Linear reads or read leases could improve performance.

## 12.11 Experiments to Try

To deepen your understanding:

1. **Split vote**: Start two servers simultaneously after killing all three. Watch them compete for votes.

2. **Partition simulation**: Use firewall rules to block traffic between specific servers. Observe leader stepping down.

3. **Append during failure**: Append entries while a follower is down, then bring it back. Count the retry messages.

4. **Term progression**: Kill the leader repeatedly. Watch term numbers increment.

5. **Log divergence**: Create a scenario where two servers have conflicting entries (requires timing manipulation). Watch reconciliation.

## Conclusion

Running the cluster demonstrates Raft in action: leader election, log replication, and failure handling. Start three servers, connect a client, append entries, and observe the message flow. Kill servers to see elections and log reconciliation. This hands-on experimentation builds intuition that reading code alone cannot provide. While this implementation has limitations, it captures the core algorithm faithfully, making it an effective learning tool.
