# Chapter 1: Introduction to Distributed Consensus

## Introduction

This chapter explains why distributed consensus exists and what problem Raft solves. Before diving into code, you need to understand the fundamental challenge: how do multiple machines agree on a shared state when any of them might fail or become unreachable at any moment?

## 1.1 The Problem of Shared State

Consider a simple key-value store. A single server handles all reads and writes—easy to reason about, but a single point of failure. If that server crashes, the service is unavailable. If its disk fails, data is lost.

The obvious solution is replication: keep copies of the data on multiple servers. But replication introduces a new problem. When a client writes a value, which server is authoritative? If servers disagree, which one is correct?

```
     Client
       │
       │ write(x=5)
       ▼
   ┌───────┐       ┌───────┐       ┌───────┐
   │Server1│       │Server2│       │Server3│
   │ x = 5 │       │ x = ? │       │ x = ? │
   └───────┘       └───────┘       └───────┘
```

Naively broadcasting writes doesn't work. Messages can be delayed, reordered, or lost. Server2 might see `x=5` before Server3 does. Or Server3 might never receive the update at all.

What you need is a way for all servers to agree on the sequence of updates. If they all apply the same updates in the same order, they'll end up in the same state. This is the consensus problem.

## 1.2 What Can Go Wrong

Distributed systems face failure modes that single-machine systems don't:

**Crashes**: A server stops responding. It might restart later with or without its previous state.

**Network partitions**: Some servers can communicate with each other but not with others. Server1 can reach Server2, but neither can reach Server3.

```
   ┌───────┐       ┌───────┐       ┌───────┐
   │Server1│◄─────►│Server2│   X   │Server3│
   └───────┘       └───────┘       └───────┘
                                   (partitioned)
```

**Message delays**: A message sent now might arrive in milliseconds, seconds, or never.

**Message reordering**: Message A sent before message B might arrive after B.

These failures can occur in any combination. A server might crash during a network partition, then recover while the partition heals. Your consensus algorithm must handle all of these correctly.

## 1.3 The Consensus Problem

Formally, a consensus algorithm must satisfy three properties:

**Agreement**: All non-faulty nodes decide on the same value. If Server1 thinks the sequence is [A, B, C] and Server2 thinks it's [A, B, D], the system is broken.

**Validity**: The decided value was proposed by some node. The system can't fabricate commands out of nowhere.

**Termination**: All non-faulty nodes eventually decide. The system can't get stuck forever (though it may be temporarily unavailable during severe failures).

The difficulty is achieving these properties despite the failure modes. A naive "just pick a leader" approach fails because:
- How do you pick a leader if servers can't communicate?
- What happens when the leader crashes?
- What if two servers both think they're the leader?

## 1.4 Raft's Approach

Raft, published in 2014, was designed to be understandable. The authors explicitly prioritized comprehensibility over novelty. Where Paxos (the previous standard) is notoriously difficult to understand, Raft decomposes the problem into three relatively independent subproblems:

**Leader election**: At any time, at most one server is the leader. The leader handles all client requests and coordinates replication. If the leader fails, a new one is elected.

**Log replication**: The leader accepts commands from clients, appends them to its log, and replicates the log to followers. Once a command is replicated on a majority of servers, it's committed and safe.

**Safety**: Raft ensures that if a command is committed, all future leaders will have that command in their logs. Committed commands are never lost.

The key insight is that with a single leader, there's no ambiguity about command ordering. The leader decides the order, and everyone else follows. The hard part is ensuring there's exactly one leader and handling transitions cleanly.

## 1.5 Terms as Logical Time

Raft uses **term numbers** as a logical clock. Terms are consecutive integers that increase monotonically. Each term begins with an election. If the election succeeds, one server becomes leader for that term. If it fails (no one gets a majority), a new term begins.

```
Time ──────────────────────────────────────────────────────►

Term 1              Term 2         Term 3       Term 4
├───────────────────┼──────────────┼────────────┼──────────
│ Election │ Leader │ Election     │ Election   │ Election
│ succeeds │ serves │ fails        │ succeeds   │ succeeds
└──────────┴────────┴──────────────┴────────────┴──────────
```

Terms serve as a conflict resolver. If two servers disagree, the one with the higher term wins. A server that has been partitioned might have an old term number; when it reconnects, it discovers the higher term and defers to current leadership.

Every message carries the sender's term. When a server receives a message with a higher term, it updates its own term and becomes a follower (if it wasn't already).

## 1.6 Guarantees and Non-Guarantees

Raft provides strong guarantees:

**Safety**: Raft never returns incorrect results. If a client receives confirmation that a command was committed, that command will be in all future leaders' logs and will be applied exactly once.

**Availability (conditional)**: If a majority of servers are functioning and can communicate with each other and with clients, the system makes progress.

Raft does not guarantee:

**Availability during severe partitions**: If the leader is partitioned from a majority, the system stalls until the partition heals.

**Performance**: Raft prioritizes correctness over speed. Every commit requires majority acknowledgment.

**Exactly-once semantics without client cooperation**: Raft ensures the log is consistent, but clients must handle retries and duplicate detection themselves.

## Conclusion

Distributed consensus ensures multiple machines agree on shared state despite failures. The problem is hard because machines can crash, networks can partition, and messages can be delayed or lost. Raft solves this by electing a leader who coordinates all changes, replicating a log of commands to followers, and using term numbers to prevent conflicts between stale and current leaders. The rest of this book shows exactly how this implementation achieves these properties.
