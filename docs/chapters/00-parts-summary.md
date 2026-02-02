# Parts Assessment

## Decision: Parts Are Warranted

With 8 chapters covering distinct phases of understanding (primitives → algorithms → runtime), parts provide useful scaffolding. The grouping reflects natural boundaries in both the codebase and the learning progression.

## Part I: Foundations

**Chapters:** 1 (Introduction), 2 (The Log), 3 (Messages), 4 (Roles and State Transitions)

This part establishes the vocabulary and building blocks. The reader learns what Raft is trying to achieve and meets the core data structures: log entries, message types, and the role enumeration. These chapters are relatively independent—you could read them in any order, though the Introduction provides useful context.

By the end of Part I, the reader understands the *pieces* of Raft without yet seeing how they fit together. They can look at a `LogEntry`, an `AppendEntryRequest`, or a `Role.CANDIDATE` and know what each represents.

## Part II: The Algorithm

**Chapters:** 5 (The State Machine), 6 (Log Replication), 7 (Leader Election)

This part covers the actual consensus algorithm. The state machine chapter introduces `RaftState`—the central class that holds state and processes messages. Then log replication and leader election explain the two core behaviors: how the leader keeps followers in sync, and how a new leader emerges when the old one fails.

These chapters build on Part I heavily. Message types become meaningful when you see which handler processes them. Role transitions make sense when you watch an election unfold.

By the end of Part II, the reader understands *why* the algorithm works—not just what it does, but why the constraints exist and what would break without them.

## Part III: Running the System

**Chapters:** 8 (Network and Runtime)

This part connects the algorithm to the real world. `RaftNode` handles network communication, `RaftServer` orchestrates the event loop, and timers drive elections. The reader sees how the clean abstractions from earlier chapters compose into a working distributed system.

Part III is shorter than the others—a single chapter—but that reflects the implementation's design. The runtime layer is intentionally thin. Most complexity lives in `RaftState`; the runtime just wires things together.

## How the Parts Connect

Part I provides the vocabulary. Part II uses that vocabulary to explain the algorithm. Part III shows the algorithm running.

A reader could skip Part I if they're already familiar with Raft concepts and just want to see this implementation. Part III makes less sense without Part II—the runtime code calls methods explained in the algorithm chapters. But the progression is designed so each part rewards reading the previous one.
