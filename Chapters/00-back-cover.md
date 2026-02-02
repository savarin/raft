# Back Cover

## The Problem This Book Solves

Distributed consensus is fundamental to building reliable systems, yet most engineers find it intimidating. The Raft paper deliberately simplifies consensus compared to Paxos, but there remains a gap between understanding the algorithm conceptually and implementing it correctly. Most resources either explain Raft abstractly or present code without illuminating the design decisions behind it.

This book bridges that gap. By walking through a working Raft implementation line by line, you develop intuition for *why* the algorithm works, not just *how* to implement it.

## Who Is This Book For?

**The intermediate programmer** comfortable with Python who wants to understand distributed systems fundamentals. You know how to work with classes, threads, and sockets. You've heard of consensus algorithms but find them mysterious.

**The curious builder** who wants to understand the systems underlying databases, coordination services, and distributed storage. You learn best by reading real code, not pseudocode.

**The engineer preparing for distributed systems work** who needs mental models for reasoning about consistency, fault tolerance, and leader election in production systems.

## What You Will Learn

1. **Leader Election**: How nodes coordinate to elect a single leader without a central authority, and why term numbers prevent split-brain scenarios.

2. **Log Replication**: How the leader replicates commands to followers while maintaining the log continuity invariant that makes Raft safe.

3. **State Machine Architecture**: How role transitions (follower, candidate, leader) are codified as explicit state changes, and why this matters for correctness.

4. **Message-Driven Design**: How to structure a distributed system around typed messages and handlers, enabling deterministic testing without network overhead.

5. **Testing Distributed Algorithms**: How to verify correctness against paper specifications (Figure 7 scenarios) without running actual distributed infrastructure.

## Why This Approach

**Code-first learning.** Each concept is introduced through the actual implementation, then explained. You see concrete code before abstract patterns.

**Direct mapping to the paper.** This implementation references specific sections of the Raft paper (Figure 2, Figure 7). You can read the paper alongside this book and see exactly how specifications become code.

**Clean layered architecture.** The implementation separates concerns clearly: log operations, role state machines, message handling, and network I/O each live in their own module. This separation reveals the algorithm's structure rather than obscuring it.

**Deterministic testing.** The test suite exercises edge cases from the paper (log reconciliation scenarios from Figure 7, the commit index safety requirement from Figure 8) without running multiple processes. You can step through the algorithm's behavior on your own machine.

## After Reading This Book

You will be able to:

- Explain Raft's safety guarantees and the invariants that preserve them
- Read the Raft paper with comprehension of how each rule translates to code
- Reason about distributed systems failures: partitions, leader crashes, split votes
- Design message-driven architectures for other distributed protocols
- Write deterministic tests for stateful, message-passing systems

---

*This implementation was developed during David Beazley's "Rafting Trip" course. The code prioritizes clarity over optimization, making it suitable for learning rather than production use.*
