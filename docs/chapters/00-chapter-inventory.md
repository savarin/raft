# Chapter Inventory

This inventory maps the natural structure of the Raft implementation to a learning path. The chapters follow the layered architecture of the codebase: primitives first, then composition, then runtime behavior.

## Chapters

1. **Introduction: What Is Raft?**
   The problem Raft solves, its place in the distributed systems landscape, and how this implementation approaches the algorithm.

2. **The Log**
   The replicated log as the foundation of consensus—its structure, invariants, and the `append_entries` operation that maintains them.

3. **Messages**
   The vocabulary of Raft: message types, their fields, and how they map to the paper's RPC definitions. Also covers serialization with Bencode.

4. **Roles and State Transitions**
   Followers, Candidates, and Leaders—what each role does, when transitions happen, and the state machine that governs them.

5. **The State Machine**
   `RaftState` as the heart of the implementation: how it processes messages, manages volatile and persistent state, and produces responses.

6. **Log Replication**
   Leader-driven replication: `nextIndex` and `matchIndex`, handling failures, and the rules for advancing `commitIndex`.

7. **Leader Election**
   How elections work: timeouts, vote requests, the safety constraints that prevent split-brain, and what makes a candidate's log "at least as up-to-date."

8. **Network and Runtime**
   `RaftNode` for communication, `RaftServer` for orchestration—how the pieces fit together into a running cluster.

## Notes

- Chapters 2-4 cover the **primitives**: log, messages, roles. These are largely independent modules.
- Chapters 5-7 cover the **algorithms**: state management, replication, election. These build on the primitives.
- Chapter 8 covers the **runtime**: how the algorithm runs in practice.

The progression mirrors how you'd build the system: understand the data structures, then the state machine logic, then how it all runs.
