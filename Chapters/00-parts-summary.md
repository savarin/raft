# Parts Summary

This book follows the layered architecture of the implementation itself. Each part builds on the previous, mirroring how the codebase separates concerns.

## Part I: Foundations

**What it covers**: The distributed consensus problem, why Raft exists, and an architectural overview of this implementation. Introduces the message-driven design pattern that structures the entire system.

**What the reader knows after**: Why consensus is hard, what Raft guarantees, and how the codebase is organized. The reader understands that this implementation separates log operations, role state machines, protocol handlers, and network I/O into distinct layers.

**Chapters**:
- Chapter 1: Introduction to Distributed Consensus
- Chapter 2: Architecture Overview

## Part II: The Replicated Log

**What it covers**: The log data structure at Raft's core. How entries are appended, why the log continuity condition matters, and how conflicts are resolved. This part covers `raftlog.py` and the encoding helpers in `rafthelpers.py`.

**What the reader knows after**: The invariants that make Raft's log safe, how `append_entries` implements the paper's specification, and how logs can diverge and be reconciled.

**Chapters**:
- Chapter 3: Log Entries and the Append Operation
- Chapter 4: Message Encoding with Bencode

## Part III: Roles and State Transitions

**What it covers**: The three roles (follower, candidate, leader) and the state machine governing transitions between them. How terms prevent split-brain scenarios. This part covers `raftrole.py` and the role-related state in `raftstate.py`.

**What the reader knows after**: When and why nodes change roles, what state must be initialized or reset on each transition, and how the implementation codifies the rules from Figure 2 of the paper.

**Chapters**:
- Chapter 5: The Role State Machine
- Chapter 6: State Attributes and Transitions

## Part IV: The Consensus Protocol

**What it covers**: The handlers that implement Raft's RPCs: AppendEntries for log replication and heartbeats, RequestVote for leader election. How the leader tracks follower progress with `nextIndex` and `matchIndex`. How `commitIndex` advances safely. This part covers the handler methods in `raftstate.py` and the message types in `raftmessage.py`.

**What the reader knows after**: How leader election works end-to-end, how log replication achieves consistency, and why the commit index safety rule (requiring entries from the current term) prevents the Figure 8 anomaly.

**Chapters**:
- Chapter 7: Message Types and the Handler Pattern
- Chapter 8: Leader Election
- Chapter 9: Log Replication and Commitment

## Part V: Network and Runtime

**What it covers**: The infrastructure that makes nodes communicate: sockets, threads, queues. How timeouts trigger elections and heartbeats. How the server combines state, network, and timer into a running node. This part covers `raftnode.py`, `raftserver.py`, and `raftclient.py`.

**What the reader knows after**: How the pure protocol logic connects to real network I/O, why message delivery is best-effort, and how to run and interact with the cluster.

**Chapters**:
- Chapter 10: Network Infrastructure
- Chapter 11: The Raft Server
- Chapter 12: Running the Cluster

---

## How Parts Connect

```
Part I: Foundations
    │
    ▼
Part II: The Replicated Log ◄─────────────────┐
    │                                         │
    ▼                                         │
Part III: Roles and State Transitions         │ (log operations
    │                                         │  used by state)
    ▼                                         │
Part IV: The Consensus Protocol ──────────────┘
    │
    ▼
Part V: Network and Runtime
```

Part I provides context. Parts II and III introduce the two foundational concepts (logs and roles) that Part IV combines into the full protocol. Part V adds the infrastructure to run it.

The reader can stop after Part IV with a complete understanding of the algorithm. Part V is for those who want to see it run.
