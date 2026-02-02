# Chapter 3: Log Entries and the Append Operation

## Introduction

This chapter covers the replicated log at Raft's core. The log is an ordered sequence of commands that all nodes must eventually agree on. The `append_entries` operation, implemented in `raftlog.py`, enforces the invariants that make this agreement safe. Understanding the log is essential—every other part of Raft exists to maintain log consistency.

## Sections

### 3.1 The LogEntry Data Structure

The `LogEntry` dataclass: a term number and a command string. Why every entry carries its term, and how this enables conflict detection.

```python
@dataclasses.dataclass
class LogEntry:
    term: int
    item: str
```

### 3.2 The Log Continuity Condition

Why logs must never have gaps. The `previous_index` and `previous_term` parameters that enforce continuity. If these don't match, the append fails.

### 3.3 Implementing append_entries

Walking through `raftlog.append_entries` step by step:
1. Check that `previous_index` doesn't create gaps
2. Verify the term at `previous_index` matches `previous_term`
3. Handle conflicts: delete divergent entries
4. Append new entries not already present

### 3.4 Conflict Resolution

When logs diverge (same index, different terms), the leader's log wins. Why deleting follower entries is safe: the leader's log represents committed truth.

### 3.5 The Figure 7 Scenarios

The Raft paper's Figure 7 shows various log states after failures. How the test suite (`test_raftlog.py`) exercises these exact scenarios.

### 3.6 Idempotency and Duplicate Handling

Why `append_entries` is safe to retry. The `is_equal_entry` check prevents duplicate appends while allowing retransmission.

## Conclusion

The replicated log stores an ordered sequence of commands. The `append_entries` operation enforces two key invariants: logs never have gaps, and entries at the same index must have the same term. When conflicts occur, the leader's entries overwrite the follower's. These invariants, verified through Figure 7 test cases, ensure all nodes eventually converge to identical logs.

---

## Cross-Chapter Coordination

**Concepts introduced here**:
- `LogEntry` dataclass (term, item)
- Log continuity condition
- `append_entries` operation
- Conflict resolution (leader wins)
- Figure 7 scenarios

**Back-references**:
- Chapter 2's module overview places `raftlog.py` at the bottom layer

**Forward dependencies**:
- Chapter 6 uses log state (`self.log`) in `RaftState`
- Chapter 9 calls `append_entries` from handlers
- Test files reference Figure 7 scenarios introduced here
