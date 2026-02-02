# Terminology Register

This document defines canonical terminology used throughout the book. Use these exact forms for consistency.

## Raft Concepts

| Canonical Form | Alternatives to Avoid | Notes |
|----------------|----------------------|-------|
| term | Term | Lowercase unless starting a sentence |
| leader | Leader | Lowercase unless starting a sentence |
| follower | Follower | Lowercase unless starting a sentence |
| candidate | Candidate | Lowercase unless starting a sentence |
| log entry | log-entry, LogEntry | Use "LogEntry" only when referring to the class |
| commit index | commitIndex | Use "commitIndex" only when referring to the variable |
| `nextIndex` | next index, next_index | Use backticks when referring to the data structure |
| `matchIndex` | match index, match_index | Use backticks when referring to the data structure |
| heartbeat | heart beat, heart-beat | One word |
| AppendEntries | Append Entries, append entries | PascalCase for the RPC name |
| RequestVote | Request Vote, request vote | PascalCase for the RPC name |

## Implementation Concepts

| Canonical Form | Alternatives to Avoid | Notes |
|----------------|----------------------|-------|
| `RaftState` | Raft State, raft state | Use backticks for class name |
| `RaftNode` | Raft Node, raft node | Use backticks for class name |
| `RaftServer` | Raft Server, raft server | Use backticks for class name |
| state machine | state-machine | Two words, no hyphen |
| message handler | message-handler | Two words, no hyphen |

## Paper References

| Canonical Form | Notes |
|----------------|-------|
| Figure 2 | Always capitalize "Figure" |
| Figure 7 | Always capitalize "Figure" |
| Figure 8 | Always capitalize "Figure" |
| the Raft paper | Not "Raft Paper" or "raft paper" |

## Code Style in Prose

- Use backticks for: variable names, function names, class names, file names
- Use **bold** for: introducing new terms on first use
- Use *italics* for: emphasis, book titles
- Use "quotes" for: colloquial terms, scare quotes

## Capitalization

- Role names (leader, follower, candidate) are lowercase in prose
- Message type names (AppendEntryRequest, RequestVoteResponse) use PascalCase
- Enum values (LEADER, FOLLOWER, CANDIDATE) use UPPER_CASE when showing code
