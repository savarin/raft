# Chapter 1: Introduction

You're about to read through a complete implementation of the Raft consensus algorithm. Before diving into the code, this chapter sets the context: what problem we're solving, why Raft exists, and how this particular implementation is structured.

## The Consensus Problem

Imagine you're building a system that stores important data—user accounts, financial transactions, configuration settings. You can't afford to lose this data, so you replicate it across multiple servers. If one server dies, another takes over.

But now you have a new problem: which server has the correct data? If a client writes to server A, then server A crashes before replicating to server B, what happens when B becomes the primary? Does it have the latest data or not?

This is the consensus problem. Multiple servers need to agree on a sequence of operations—and they need to agree even when servers crash, networks partition, and messages arrive out of order. A value that's been "committed" must never be lost, even if the server that committed it immediately fails.

You might think a database handles this, but databases face the same problem internally. MySQL's group replication, PostgreSQL's streaming replication, etcd's key-value store—they all need consensus mechanisms. Raft is one of those mechanisms.

The challenge isn't just agreeing—it's agreeing safely and efficiently. A naive approach might require all servers to respond before committing, but that means one slow or failed server blocks everything. Raft achieves consensus with only a majority of servers, tolerating failures of the minority.

## Why Raft Exists

Before Raft, the dominant consensus algorithm was Paxos. Paxos is provably correct, but it has a reputation: difficult to understand, difficult to implement correctly. Leslie Lamport's original paper describes the algorithm through the metaphor of a Greek parliament, which obscures more than it clarifies.

The Raft paper—"In Search of an Understandable Consensus Algorithm" by Diego Ongaro and John Ousterhout—has a different goal. The authors explicitly optimized for understandability. They wanted an algorithm that students could learn, that engineers could implement, and that operators could reason about when things go wrong.

Raft achieves consensus through two mechanisms:

1. **Leader election**: At any time, at most one server is the "leader." The leader accepts client requests and replicates them to other servers. When a leader fails, the remaining servers elect a new one.

2. **Log replication**: The leader maintains a log of commands. It sends log entries to followers, who append them to their own logs. Once a majority of servers have the entry, it's committed and can't be lost.

The paper's insight is that separating these concerns—who's in charge vs. how data propagates—makes the algorithm easier to understand than Paxos's single monolithic protocol.

## The Raft Paper and Figure 2

The Raft paper is well-written, but there's a gap between reading it and implementing it. The paper presents the algorithm as a state machine, summarized in Figure 2—a dense box of rules that fit on a single page.

Figure 2 tells you *what* to implement:

- **Persistent state**: currentTerm, votedFor, log[]
- **Volatile state**: commitIndex, lastApplied, nextIndex[], matchIndex[]
- **AppendEntries RPC**: arguments, results, receiver implementation
- **RequestVote RPC**: arguments, results, receiver implementation
- **Rules for servers**: what each role does, when to convert between roles

What Figure 2 doesn't tell you is *how*. It doesn't specify:

- How to structure your code—one class or many?
- How to handle network communication—blocking or async?
- How to manage timeouts—threads, event loops, something else?
- How to test the algorithm without running real servers

This implementation makes specific choices for each of these questions. Those choices aren't the only valid ones, but understanding them helps you understand both the code and the algorithm.

Throughout this book, you'll find references to Figure 2. The docstrings in the source code quote it extensively:

```python
# From raftstate.py
"""
State section in Figure 2 of Raft paper (minor divergence from 1-indexing in
paper vs 0-indexing implementation):

Persistent state on all servers:
currentTerm     latest term server has seen (initialized to 0 on first boot,
                increases monotonically)
votedFor        candidateId that received vote in current term (or null if none)
log[]           log entries; each entry contains command for state machine, and
                term when entry was received by leader (first index is 1)
"""
```

The code and the paper are meant to be read together.

## This Implementation's Approach

This implementation separates the Raft algorithm from the concerns of running it:

```
raftstate.py     The algorithm: state, handlers, transitions
raftlog.py       The log: entries, append logic, invariants
raftrole.py      Role definitions and state change rules
raftmessage.py   Message types and serialization
raftnode.py      Network: sockets, threads, queues
raftserver.py    Orchestration: combines state, network, timers
```

The most important file is `raftstate.py`. It contains `RaftState`, the class that holds all Raft state and processes all messages. If you understand `RaftState`, you understand the algorithm.

The separation matters for testability. You can create a `RaftState`, feed it messages directly, and verify the resulting state—no network, no threads, no timers. The tests in `test_raftstate.py` do exactly this. They simulate message exchanges that would happen in a real cluster and verify that the state evolves correctly.

The implementation uses pure Python with no external dependencies beyond the standard library. This is a deliberate choice: fewer moving parts, easier to read, nothing to install. The cost is that it's not production-grade—there's no persistence, no encryption, no authentication. But for understanding the algorithm, simplicity wins.

## Running the Cluster

The README walks you through running a three-node cluster. Here's the quick version:

Start three servers in separate terminals:

```bash
python src/raftserver.py 1
python src/raftserver.py 2
python src/raftserver.py 3
```

Start a client:

```bash
python src/raftclient.py 0
```

The server prompts are color-coded by role:

- **Red**: Follower—waiting for a leader
- **Yellow**: Candidate—trying to get elected
- **Green**: Leader—accepting commands

When you start the cluster, all servers begin as followers (red). After a timeout, one becomes a candidate and requests votes. If it gets a majority, it becomes leader (green).

From the client, you can send commands:

```
0 > 1 append a b c    # Tell server 1 to append entries a, b, c
0 > self              # Query all servers' state
```

Try stopping the leader (Ctrl+C). Watch another server become candidate, then leader. This is Raft's fault tolerance in action.

## Reading This Book

The book is organized into three parts:

**Part I: Foundations** (Chapters 1-4) introduces the building blocks: what logs are, what messages exist, what roles servers can have. These chapters are relatively independent—you can read them in any order, though the Introduction provides useful context.

**Part II: The Algorithm** (Chapters 5-7) covers the actual consensus protocol. The state machine chapter shows how messages are processed. Log replication explains how the leader keeps followers synchronized. Leader election explains how new leaders emerge.

**Part III: Running the System** (Chapter 8) connects the algorithm to the real world: network code, timers, the event loop.

Each chapter shows code from the implementation. I recommend having the source code open as you read—either in your editor or from the repository. The chapters reference specific files and line numbers.

## Conclusion

Raft solves the consensus problem: getting distributed servers to agree on a sequence of operations, even when some servers fail. It does this through leader election (one server is in charge) and log replication (the leader propagates commands to followers).

This implementation separates the algorithm (`raftstate.py`) from the runtime concerns (`raftnode.py`, `raftserver.py`). The separation enables testing: you can verify the algorithm's correctness by feeding it messages directly, without running real servers.

You can run the code yourself: three servers, one client, colored prompts showing roles. Kill a leader and watch another take over.

The next chapter examines the log—the data structure at the heart of Raft. Every command passes through the log; consensus means agreeing on its contents.
