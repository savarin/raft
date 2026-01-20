# Chapter 1: The Problem of Consensus

*In which we discover why getting computers to agree is surprisingly hard, why the famous solution was famously incomprehensible, and how a protocol designed for understandability became one of the most important ideas in distributed systems.*

---

## The Illusion of the Single Machine

When you write code that runs on a single computer, you operate under a comforting illusion: that there is one truth. A variable has one value. A file contains one sequence of bytes. When you read after a write, you see what you wrote.

This illusion shatters the moment you try to build anything that matters.

Consider a banking system. You have customer data—account balances, transaction histories, personal information. This data must survive hardware failures, so you replicate it across multiple servers. Now you have a problem: when a customer transfers money, which server is the source of truth? What happens if two servers disagree about an account balance? What if a network partition means half your servers can't communicate with the other half?

Or consider a configuration service for a large distributed application. Hundreds of servers need to agree on which database server is the primary. If they disagree—if some servers think Server A is primary while others think it's Server B—you get "split-brain": two servers both accepting writes, their data diverging irreconcilably.

These aren't hypothetical concerns. They're the reason your bank doesn't lose your money when a data center catches fire. They're why Google can serve your search results even when entire regions go offline. They're the foundation beneath every reliable distributed system you've ever used.

The solution to these problems has a name: **consensus**.

---

## What Is Consensus?

Consensus is the problem of getting multiple computers to agree on a single value, even when some of them might fail or become unreachable.

This sounds simple. It is not.

The difficulty lies in the constraints. A consensus algorithm must satisfy three properties:

1. **Agreement**: All non-failed nodes must agree on the same value.
2. **Validity**: The agreed-upon value must have been proposed by some node (no making up values).
3. **Termination**: The algorithm must eventually complete, even if some nodes fail.

The challenge is achieving these properties in the face of:

- **Crash failures**: Servers can stop working at any moment, with no warning.
- **Network partitions**: Communication between servers can fail, splitting the cluster into isolated groups.
- **Asynchrony**: Messages can be delayed arbitrarily. You can't tell the difference between a slow server and a dead one.

The impossibility result known as FLP (after Fischer, Lynch, and Paterson) proved in 1985 that in a purely asynchronous system, no consensus algorithm can guarantee all three properties if even a single node might fail. This isn't a limitation of our current algorithms—it's a fundamental impossibility.

So how do practical systems achieve consensus? By relaxing the assumptions slightly. Real networks aren't purely asynchronous—we can use timeouts to detect likely failures. This opens the door to algorithms that work correctly in practice, even if they can't provide theoretical guarantees in all possible scenarios.

---

## The Shadow of Paxos

For decades, the canonical answer to consensus was **Paxos**, invented by Leslie Lamport in 1989 and published in a paper titled "The Part-Time Parliament" in 1998.

Paxos is provably correct. It's also notoriously difficult to understand.

Lamport originally presented Paxos as a story about legislators on a Greek island reaching agreement despite their unreliable attendance. The metaphor was meant to make the algorithm more accessible. Instead, it confused nearly everyone who read it.

In 2001, Lamport published "Paxos Made Simple," which begins with the sentence: "The Paxos algorithm, when presented in plain English, is very simple." The paper is seven pages long. The algorithm is not, in fact, simple.

The problem with Paxos isn't that it's wrong—it's that it's incomplete. The basic algorithm (now called "Single-Decree Paxos") reaches agreement on a single value. Real systems need to agree on a *sequence* of values: a log of commands to execute. The extension to multiple values ("Multi-Paxos") was never fully specified by Lamport. Every implementation has to figure out the details independently.

The result was decades of confusion. Researchers struggled to understand Paxos. Practitioners struggled to implement it. Google's Chubby paper (2006) noted that "there are significant gaps between the description of the Paxos algorithm and the needs of a real-world system... the final system will be based on an unproven protocol."

Something had to change.

---

## Raft: Consensus for Mortals

In 2014, Diego Ongaro and John Ousterhout at Stanford published "In Search of an Understandable Consensus Algorithm." Their protocol, **Raft**, was designed with a radical premise: understandability is a legitimate design goal.

This wasn't just philosophical. Ongaro and Ousterhout conducted user studies comparing Raft and Paxos. Students who learned Raft answered quiz questions more accurately. More importantly, they could *reason* about the algorithm—predict its behavior in edge cases, identify bugs in faulty implementations.

Raft achieves this understandability through **decomposition**. Where Paxos presents consensus as a single monolithic problem, Raft breaks it into three relatively independent subproblems:

1. **Leader election**: How do servers choose a leader to coordinate all decisions?
2. **Log replication**: How does the leader distribute commands to followers?
3. **Safety**: What guarantees prevent the system from reaching inconsistent states?

Each subproblem can be understood in isolation. The interactions between them are carefully minimized. The result is an algorithm that you can fit in your head.

The Raft paper's Figure 2 is famous in distributed systems. It summarizes the entire algorithm on a single page—all the state, all the rules, all the message types. This isn't a simplification or an overview. It's the complete specification.

The implementation in this book follows that specification directly. When the code references "Figure 2" or "§5.3," it's pointing to the exact passage in the paper that defines that behavior. This traceability is a feature, not an accident.

---

## The Three Roles

A Raft cluster consists of servers, each of which is always in one of three states:

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    │   times out,        discovers leader    │
                    │   starts election   or new term         │
                    │         │                 │             │
                    │         ▼                 │             │
┌──────────┐     timeout     ┌───────────┐     │     ┌───────────┐
│          │ ───────────────▶│           │─────┘     │           │
│ FOLLOWER │                 │ CANDIDATE │           │  LEADER   │
│          │◀────────────────│           │──────────▶│           │
└──────────┘  discovers      └───────────┘  wins     └───────────┘
      ▲       leader or              ▲      election       │
      │       higher term            │                     │
      │                              │                     │
      └──────────────────────────────┴─────────────────────┘
                      discovers server with higher term
```

**Followers** are passive. They issue no requests on their own; they simply respond to requests from leaders and candidates. When a cluster is operating normally, there is one leader and all other servers are followers.

**Candidates** are followers who have grown impatient. If a follower doesn't hear from a leader within a timeout period, it assumes the leader has failed and attempts to become the new leader by soliciting votes from the cluster.

**Leaders** handle all client requests. They replicate commands to followers, decide when commands are committed, and send periodic heartbeats to maintain their authority.

This role structure appears directly in the implementation:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
```

The simplicity is intentional. At any moment, a server's behavior is determined entirely by its role. Followers respond to messages. Candidates solicit votes. Leaders replicate logs. There are no complex state machines, no subtle modes within modes.

---

## Terms: Logical Time in a Distributed World

How do you tell time in a distributed system? Physical clocks are unreliable—servers' clocks drift, network delays are unpredictable, and you can never be certain that "now" on one machine means the same thing as "now" on another.

Raft solves this with **terms**: monotonically increasing integers that act as logical epochs.

```
      Term 1          Term 2          Term 3          Term 4
    ──────────────────────────────────────────────────────────▶
                                                          time

    ┌──────────┐    ┌──────────┐    ┌────────────────────────
    │ Election │    │ Election │    │     Normal operation
    │ (no      │    │ S2 wins  │    │     S2 is leader
    │ winner)  │    │          │    │
    └──────────┘    └──────────┘    └────────────────────────
```

Each term begins with an election. If the election succeeds, the winner leads for the rest of the term. If the election fails (perhaps due to split votes), the term ends with no leader, and a new election begins immediately.

Terms serve as a universal clock for the cluster:

- **Stale detection**: If a server receives a message with a term higher than its own, it knows its information is out of date. It immediately updates its term and reverts to follower state.

- **Conflict resolution**: When servers disagree, the one with the higher term wins. There are no ties—terms are strictly ordered.

- **Leader legitimacy**: A leader is legitimate only during its term. If a partitioned leader rejoins the cluster and discovers a higher term exists, it immediately abdicates.

The implementation tracks each server's current term as persistent state:

```python
@dataclasses.dataclass
class RaftState:
    identifier: int

    def __post_init__(self) -> None:
        # ...
        self.current_term: int = -1
        # ...
```

The docstring at the top of `raftstate.py` quotes the Raft paper directly:

> **currentTerm**: latest term server has seen (initialized to 0 on first boot, increases monotonically)

This direct correspondence between specification and implementation is maintained throughout the codebase. When you read the code, you're reading the algorithm.

---

## The Log: A Sequence of Commands

At the heart of Raft is the **replicated log**: an ordered sequence of commands that all servers must execute in the same order.

```
    Index:    0      1      2      3      4      5      6
            ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐
    Server1 │ x←3  │ y←1  │ x←2  │ y←9  │ x←7  │ y←2  │      │
    (Leader)│ t=1  │ t=1  │ t=1  │ t=2  │ t=3  │ t=3  │      │
            ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
    Server2 │ x←3  │ y←1  │ x←2  │ y←9  │ x←7  │      │      │
            │ t=1  │ t=1  │ t=1  │ t=2  │ t=3  │      │      │
            ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
    Server3 │ x←3  │ y←1  │ x←2  │ y←9  │      │      │      │
            │ t=1  │ t=1  │ t=1  │ t=2  │      │      │      │
            └──────┴──────┴──────┴──────┴──────┴──────┴──────┘
                                   ▲
                                   │
                              committed
                           (replicated on
                             majority)
```

Each log entry contains:
- A **command** to execute (like "set x to 3")
- The **term** when the entry was received by the leader
- An implicit **index** (its position in the log)

The implementation represents this cleanly:

```python
@dataclasses.dataclass
class LogEntry:
    term: int
    item: str
```

The log serves multiple purposes:

1. **Durability**: Once an entry is committed, it survives any failure that doesn't destroy a majority of the cluster.

2. **Ordering**: All servers apply commands in log order. If server A has executed entry 5, it has definitely executed entries 0-4.

3. **Consistency**: The "Log Matching Property" guarantees that if two servers have an entry at the same index with the same term, their logs are identical up to that point.

This last property is subtle and crucial. It means you never need to compare entire logs—a single matching entry proves everything before it also matches.

---

## State: What Servers Remember

Each Raft server maintains several pieces of state, carefully categorized by the paper:

### Persistent State (survives restarts)

| Field | Description |
|-------|-------------|
| `currentTerm` | Latest term the server has seen |
| `votedFor` | Candidate that received this server's vote in the current term (if any) |
| `log[]` | Log entries |

### Volatile State (all servers)

| Field | Description |
|-------|-------------|
| `commitIndex` | Index of highest log entry known to be committed |
| `lastApplied` | Index of highest log entry applied to state machine |

### Volatile State (leaders only)

| Field | Description |
|-------|-------------|
| `nextIndex[]` | For each server, index of next log entry to send |
| `matchIndex[]` | For each server, index of highest entry known to be replicated |

The implementation mirrors this categorization:

```python
@dataclasses.dataclass
class RaftState:
    identifier: int

    def __post_init__(self) -> None:
        # Persistent state
        self.log: List[raftlog.LogEntry] = []
        self.current_term: int = -1
        self.voted_for: Optional[int] = None

        # Volatile state (all servers)
        self.commit_index: int = -1

        # Volatile state (leaders)
        self.next_index: Optional[Dict[int, int]] = None
        self.match_index: Optional[Dict[int, Optional[int]]] = None
```

Notice how the leader-only state (`next_index`, `match_index`) is `Optional`—it's `None` when the server isn't a leader. This makes the invariant explicit: only leaders track where followers are in the log.

---

## State Transitions: The Heart of the Algorithm

The most intricate part of Raft is managing state transitions—when does a follower become a candidate? When does a candidate become a leader? When must a leader step down?

The implementation encodes these transitions explicitly in `raftrole.py`:

```python
def evaluate_role_change(
    source_role: Role, source_term: int,
    target_role: Role, target_term: int
) -> Tuple[Optional[Tuple[Role, Role]], int, Operation]:
```

This function takes the role and term of both the message sender (source) and receiver (target), then determines:
1. Whether a role change should occur
2. What the new term should be
3. Whether `voted_for` should be reset

The key insight is that all role changes are triggered by comparing terms:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TERM COMPARISON RULES                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   If message term > my term:                                        │
│       → Update my term to message term                              │
│       → Reset votedFor (new term = new election)                    │
│       → If I was leader or candidate, become follower               │
│                                                                     │
│   If message term < my term:                                        │
│       → Reject the message (it's from a stale leader)               │
│       → Remain in current state                                     │
│                                                                     │
│   If message term = my term:                                        │
│       → Process normally based on message type                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

This rule—"always defer to higher terms"—is the mechanism that prevents split-brain. If two leaders somehow exist simultaneously, one must have a lower term than the other. The moment the lower-term leader receives a message from the higher-term leader, it steps down.

---

## The Two RPCs

Raft requires only two types of remote procedure calls to achieve consensus:

### AppendEntries

Sent by leaders to:
1. Replicate log entries to followers
2. Serve as heartbeats (when sent with no entries)

```python
@dataclasses.dataclass
class AppendEntryRequest(Message):
    current_term: int      # Leader's term
    previous_index: int    # Index of entry before new ones
    previous_term: int     # Term of previous entry
    entries: List[raftlog.LogEntry]  # Entries to store (empty for heartbeat)
    commit_index: int      # Leader's commit index
```

The `previous_index` and `previous_term` fields implement the Log Matching Property. Before accepting new entries, a follower verifies that it has an entry at `previous_index` with term `previous_term`. If not, the append fails, and the leader must retry with earlier entries.

### RequestVote

Sent by candidates to gather votes during elections:

```python
@dataclasses.dataclass
class RequestVoteRequest(Message):
    current_term: int      # Candidate's term
    last_log_index: int    # Index of candidate's last entry
    last_log_term: int     # Term of candidate's last entry
```

The `last_log_index` and `last_log_term` fields ensure that candidates with incomplete logs can't win elections. A server only grants its vote if the candidate's log is "at least as up-to-date" as its own—meaning the candidate's last entry has a higher term, or the same term with an equal or greater index.

---

## A Taste of the Implementation

To make this concrete, let's trace through what happens when the leader sends a heartbeat:

```python
def handle_leader_heartbeat(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:
    """
    Leader heartbeat. Send AppendEntries to all followers.
    """
    if self.role != raftrole.Role.LEADER:
        raise Exception("Not able to generate leader heartbeat when not leader.")

    followers = followers or self.create_followers_list()
    messages: List[raftmessage.Message] = []

    for follower in followers:
        message = raftmessage.AppendEntryRequest(
            self.identifier,
            follower,
            *self.create_append_entries_arguments(follower),
        )
        messages.append(message)

    return messages
```

The leader iterates through its followers and creates an `AppendEntryRequest` for each. The `create_append_entries_arguments` method determines what entries each follower needs:

```python
def create_append_entries_arguments(
    self, target: int
) -> Tuple[int, int, int, List[raftlog.LogEntry], int]:
    assert self.next_index is not None
    next_index = self.next_index[target]
    previous_index = next_index - 1
    previous_term = (
        self.log[previous_index].term
        if len(self.log) > 0 and previous_index >= 0
        else -1
    )

    return (
        self.current_term,
        previous_index,
        previous_term,
        self.log[next_index:],  # All entries from next_index onwards
        self.commit_index,
    )
```

For a heartbeat (when the follower is caught up), `next_index` equals the log length, so `self.log[next_index:]` is empty. For a follower that's behind, this slice contains the missing entries.

When a follower receives this message, it calls `handle_append_entries_request`, which:

1. Checks whether to change state based on the leader's term
2. Verifies the log consistency check (`previous_index`, `previous_term`)
3. Appends any new entries
4. Updates its commit index
5. Returns a response indicating success or failure

If the consistency check fails, the leader decrements `next_index` for that follower and retries. This backtracking continues until the leader finds a point where the logs match, then fills in all the missing entries from there.

---

## The Network Layer

The implementation includes a complete network layer that demonstrates how Raft operates in practice:

```python
@dataclasses.dataclass
class RaftNode:
    """
    Represents environment that sends/receives raw messages in the cluster.

    To send a message to any other node in the cluster, use `send`. This
    operation is non-blocking and returns immediately. There is no guarantee
    of message delivery.

    > node.send(1, b"hello")

    To receive a single message, use `receive`. This is a blocking operation
    that waits for a message to arrive from anywhere.

    > message = node.receive()
    """
```

The key insight is in the comment: **"There is no guarantee of message delivery."**

Raft is designed to work over unreliable networks. Messages can be lost, duplicated, or reordered. The algorithm handles this by:

1. **Heartbeats**: Leaders send periodic heartbeats. Lost heartbeats don't cause data loss—the next one will arrive eventually.

2. **Retries**: If a follower rejects an append (due to log inconsistency), the leader automatically retries with earlier entries.

3. **Idempotence**: Appending the same entry twice has the same effect as appending it once.

This design means Raft works over TCP, UDP, or any unreliable transport. The algorithm is resilient to the medium.

---

## Running a Cluster

The implementation is fully functional. You can start a three-server cluster with:

```
Terminal 1: python src/raftserver.py 1
Terminal 2: python src/raftserver.py 2
Terminal 3: python src/raftserver.py 3
```

Each server starts as a follower (red prompt). After the election timeout, one will become a candidate (yellow prompt) and then, upon winning the election, the leader (green prompt).

Start a client to interact with the cluster:

```
Terminal 4: python src/raftclient.py 0
0 > 1 append a b c
```

This tells server 1 to append entries "a", "b", and "c" to its log. The leader will replicate these entries to all followers.

To see the internal state of all servers:

```
0 > self
```

This prints each server's current term, log, commit index, and other state—invaluable for understanding how the algorithm operates.

---

## What We've Learned

This chapter has introduced the fundamental concepts of distributed consensus and the Raft algorithm:

- **Consensus** is the problem of getting multiple computers to agree, despite failures.
- **Raft** solves consensus through decomposition: leader election, log replication, and safety properties.
- **Terms** provide logical time, preventing split-brain by ensuring all servers agree on which leader is current.
- **The replicated log** stores commands in order, guaranteeing all servers execute the same commands in the same sequence.
- **State** is carefully categorized as persistent (survives restarts) or volatile (rebuilt after crashes).
- **Two RPCs**—AppendEntries and RequestVote—are sufficient for the entire algorithm.

We've also seen how the implementation maps directly to the specification. When the code references "Figure 2" or "§5.3," it's pointing to the exact text that defines the behavior. This traceability isn't incidental—it's the implementation's most important property.

---

## Looking Ahead

The next three chapters will dive deep into each of Raft's subproblems:

**Chapter 2: Leader Election** explores how candidates request votes, how servers decide whether to grant them, and how the cluster recovers from failed elections. We'll trace through specific scenarios: a clean election, a split vote, and what happens when a partitioned leader rejoins the cluster.

**Chapter 3: Log Replication** examines the heartbeat and append mechanism in detail. We'll work through the famous "Figure 7" scenarios from the Raft paper, showing how the implementation handles logs that have diverged due to various failure patterns.

**Chapter 4: From Paper to Production** discusses the practical aspects: the network layer, message serialization, timeouts, and testing strategies. We'll also explore what this implementation intentionally omits (snapshots, membership changes) and why.

By the end, you'll be able to read the complete Raft specification (Figure 2 of the paper) and trace every line to its implementation. You'll understand not just *what* Raft does, but *why* each rule exists and what would go wrong without it.

---

## Further Reading

**The Raft Paper**
Ongaro, D., & Ousterhout, J. (2014). "In Search of an Understandable Consensus Algorithm." *USENIX Annual Technical Conference.*

The paper is remarkably readable for an academic publication. The extended version includes proofs of safety properties and additional discussion of design decisions.

**The Raft Visualization**
https://raft.github.io/

An interactive visualization that shows Raft operating in real-time. Invaluable for building intuition about how the algorithm behaves.

**The FLP Impossibility Result**
Fischer, M. J., Lynch, N. A., & Paterson, M. S. (1985). "Impossibility of distributed consensus with one faulty process." *Journal of the ACM.*

The foundational result that shapes all practical consensus algorithms. Challenging but rewarding.

**Designing Data-Intensive Applications**
Kleppmann, M. (2017). O'Reilly Media.

Chapter 9 ("Consistency and Consensus") provides excellent context on where Raft fits in the broader landscape of distributed systems.

---

## Exercises

1. **Term Ordering**: In the implementation, what happens if a leader receives an AppendEntriesResponse with a term higher than its own? Trace through the code in `handle_append_entries_response` and `evaluate_role_change` to find out.

2. **Stale Candidates**: Consider a candidate that is partitioned from the cluster. It keeps incrementing its term and calling elections that never succeed. When it rejoins the cluster, what happens? Is this a problem?

3. **The Necessity of Terms**: Imagine a version of Raft without terms—servers simply track who the current leader is. Construct a scenario where this leads to split-brain (two servers both believing they are the leader and accepting writes).

4. **Log Matching**: The Log Matching Property states that if two logs contain an entry with the same index and term, then the logs are identical in all entries up through that index. Why is this property so useful? What would the algorithm look like without it?

5. **Hands-On**: Start a three-node cluster. Kill the leader (Ctrl-C). Observe the remaining servers elect a new leader. Restart the killed server. What role does it assume? What is its term?

---

*The next chapter begins our deep dive into leader election—the mechanism by which a leaderless cluster establishes authority.*
