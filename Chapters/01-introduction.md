# Chapter 1: Introduction to Distributed Consensus

## Introduction

This chapter explains why distributed consensus exists and what problem Raft solves. Before diving into code, you need to understand the fundamental challenge: how do multiple machines agree on a shared state when any of them might fail or become unreachable at any moment?

## Sections

### 1.1 The Problem of Shared State

Why distributed systems need consensus. The challenge of maintaining consistency across multiple machines without a single point of failure.

### 1.2 What Can Go Wrong

Failure modes in distributed systems: crashes, network partitions, message delays. Why naive approaches like "just pick a leader" fail.

### 1.3 The Consensus Problem

Formal definition of consensus: agreement, validity, termination. What it means for a distributed system to be "correct."

### 1.4 Raft's Approach

How Raft simplifies consensus compared to Paxos. The key insight: decompose consensus into leader election, log replication, and safety.

### 1.5 Guarantees and Non-Guarantees

What Raft promises: safety (never returning wrong results), liveness under certain conditions. What it doesn't promise: availability during partitions, performance.

## Conclusion

Distributed consensus ensures multiple machines agree on shared state despite failures. Raft achieves this by electing a leader who coordinates all changes, replicating a log of commands to followers, and using term numbers to prevent conflicts. The rest of this book shows exactly how.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Consensus problem (agreement, validity, termination)
- Leader-based replication
- Terms as logical clocks
- Safety vs. liveness

**Back-references**: None (first chapter)

**Forward dependencies**:
- Chapter 2 references the three components (election, replication, safety)
- Chapter 5 builds on role definitions introduced here
- Chapter 8 implements leader election sketched here
