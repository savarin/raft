# Talk Proposal: Understanding Raft

## The One Thing

Raft achieves distributed consensus through a single mechanism—leader authority backed by term numbers—that makes election, replication, and safety all follow from the same invariant.

## Audience

Recurse Center peers: technically sophisticated programmers with varying distributed systems experience. Some have built distributed systems; others have heard of Paxos but never implemented consensus. They'll ask hard questions and appreciate honest treatment of trade-offs.

**Assumed knowledge:**
- Basic networking (servers, messages, failure modes)
- Familiarity with state machines
- Comfort reading Python

**Not assumed:**
- Prior exposure to consensus algorithms
- Knowledge of Paxos or Raft specifics

## Problem

Distributed systems need agreement. When multiple servers must agree on a sequence of operations—who's the leader, what's in the log, which writes are durable—getting this wrong means data loss or split-brain scenarios. Paxos solves this but is notoriously difficult to understand and implement correctly. Raft was designed explicitly for understandability: can we build consensus that engineers can actually reason about?

## Duration

20 minutes (targeting 18-25 slides)

## Call to Action

After this talk, attendees should be able to:
1. Trace through a Raft election and explain why it's safe
2. Explain how log replication maintains consistency across failures
3. Read the Raft paper with confidence in the core concepts
4. Consider implementing Raft themselves as a learning exercise

## Why This Talk

This implementation was built as part of David Beazley's Rafting Trip class. The code cleanly separates the consensus algorithm from networking concerns, making it possible to show real code that matches the paper's concepts. The talk uses actual implementation code to ground abstract concepts.
