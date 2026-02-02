# Chapter 2: Architecture Overview

## Introduction

This chapter maps Raft's conceptual components to the codebase structure. Understanding the architecture helps you navigate the implementation and see how each module contributes to the whole. The design separates concerns into distinct layers: log operations, role state machines, protocol handlers, message types, and network I/O.

## Sections

### 2.1 Module Overview

The nine source files and their responsibilities. How `raftlog`, `raftrole`, `raftstate`, `raftmessage`, `raftnode`, `raftserver`, `raftclient`, `raftconfig`, and `rafthelpers` relate to each other.

### 2.2 The Layered Design

```
┌─────────────────────────────────────┐
│          raftserver.py              │  Runtime: timers, event loop
├─────────────────────────────────────┤
│          raftnode.py                │  Network: sockets, threads, queues
├─────────────────────────────────────┤
│          raftstate.py               │  Protocol: handlers, state management
├─────────────────────────────────────┤
│   raftrole.py    │  raftmessage.py  │  Primitives: roles, messages
├──────────────────┼──────────────────┤
│          raftlog.py                 │  Core: log operations
└─────────────────────────────────────┘
```

Why this separation matters. Each layer depends only on layers below it.

### 2.3 Message-Driven Architecture

How the system communicates through typed messages rather than direct method calls. The `handle_message` dispatch pattern in `raftstate.py`.

### 2.4 State vs. Behavior

The distinction between `RaftState` (what a node knows) and handlers (what a node does). Why stateful objects with pure handler functions enable deterministic testing.

### 2.5 Following the Paper

How this implementation maps to Figure 2 of the Raft paper. The docstrings reference specific sections (§5.1, §5.2, etc.) for traceability.

## Conclusion

The codebase separates Raft into layers: log operations at the bottom, role and message primitives above that, protocol handlers managing state, and network/runtime at the top. This separation enables testing the protocol logic without network overhead and makes each component's responsibility clear.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- Module responsibilities and dependencies
- Layered architecture pattern
- Message-driven design
- `handle_message` dispatch pattern
- Paper-to-code mapping (Figure 2 references)

**Back-references**:
- Chapter 1's three Raft components map to specific modules here

**Forward dependencies**:
- Every subsequent chapter references the module it covers
- Chapter 7 expands on message-driven architecture
- Chapter 11 expands on the runtime layer
