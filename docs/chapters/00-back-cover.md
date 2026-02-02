# Back Cover

## The Problem This Book Solves

Distributed consensus is one of the hardest problems in computer science—and one of the most misunderstood. You can read the Raft paper and understand the algorithm intellectually, but there's a gap between understanding the protocol and *building* it. How do you translate Figure 2's pseudocode into working code? What decisions does the paper leave unspecified? Where do the subtle bugs hide?

This book bridges that gap by walking through a complete, working Raft implementation in Python. Not a toy example—a real implementation with network communication, timeouts, log replication, and leader election. By the end, you'll understand not just *what* Raft does, but *why* it works and how to build it yourself.

## Who This Book Is For

You're a software engineer who has read (or tried to read) the Raft paper. Maybe you've built distributed systems before; maybe you haven't. Either way, you want to understand consensus at a deeper level than "use etcd" or "Raft is like Paxos but understandable."

You should be comfortable reading Python code. The implementation uses modern Python features (dataclasses, pattern matching, type hints), but nothing exotic. If you can follow along with well-structured Python, you can follow this book.

You're curious about *why* things are built the way they are. You don't just want to see working code—you want to understand the design decisions, the trade-offs, and what would break if you did things differently.

## What You'll Learn

1. **How to translate a distributed systems paper into code.** The Raft paper is well-written, but it's still a research paper. You'll see how its abstractions map to concrete data structures and message handlers.

2. **The architecture of a consensus implementation.** Clean separation between state machine logic, message serialization, and network I/O. Why this separation matters and how it enables testing.

3. **How log replication actually works.** The subtleties of `nextIndex` and `matchIndex`, why the leader can only commit entries from its current term, and how the algorithm recovers from failures.

4. **Where the edge cases hide.** Election safety, the split-brain scenario, what happens when messages arrive out of order. The tests that prove your implementation is correct.

5. **How to think about distributed systems.** Timeouts, idempotency, the difference between safety and liveness. Patterns you'll use in any distributed system, not just Raft.

## Why This Approach

Most distributed systems resources fall into two categories: theoretical treatments that stay abstract, or production systems that are too complex to learn from. This book takes a different approach.

The implementation is real but minimal. Every line of code serves the algorithm—no frameworks, no dependencies beyond Python's standard library, no distractions. You can run a three-node cluster on your laptop and watch leader elections happen.

The focus is on *understanding*. Each design decision is explained in terms of the problem it solves. When there are trade-offs, we name them. When the paper is ambiguous, we discuss the choices.

This book treats you as a colleague, not a student. We'll work through the hard parts together.
