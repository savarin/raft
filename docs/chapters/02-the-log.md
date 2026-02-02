# Chapter 2: The Log

## What This Chapter Covers

The replicated log is Raft's core data structure. Every command passes through the log; consensus means agreeing on the log's contents. This chapter examines the log's structure, the invariants that keep it consistent, and the `append_entries` function that maintains those invariants.

Understanding the log is prerequisite to understanding everything else. Log replication (Chapter 6) is about keeping logs synchronized across servers. Elections (Chapter 7) use log state to decide who can become leader. The state machine (Chapter 5) processes messages that read and modify the log.

## Sections

### Log Entries

The `LogEntry` dataclass: term and item. Why entries need term numbers—they identify which leader created them. The item as an opaque command (in this implementation, just a string).

### The Log as a List

Logs are Python lists of `LogEntry` objects. 0-indexing versus the paper's 1-indexing—where this matters and where it doesn't. Why `previous_index = -1` represents "before the first entry."

### The Log Continuity Invariant

The key constraint: a log can never have gaps. Each append must reference the immediately preceding entry. Why this matters for consistency—if two logs agree at index N, they agree on all entries before N.

### Conflict Resolution

When entries conflict: same index, different terms. The later term wins. Why this is safe—there's only one leader per term. The code that deletes conflicting entries and everything after them.

### The `append_entries` Function

Walking through `raftlog.append_entries` line by line. The validation steps: checking for gaps, checking term matches. The conflict resolution step. The actual append. Why it returns a boolean.

### Idempotency

Duplicate appends have no adverse effect. The same entries sent twice result in the same log. Why this matters in a network where messages can be duplicated or retried.

## Conclusion

The log's simplicity is deceptive. It's just a list of entries, but the invariants it maintains—no gaps, term-based conflict resolution, idempotency—are what make Raft work. The `append_entries` function encodes the paper's Figure 2 rules in about 30 lines of Python. With the log understood, you're ready to see how servers communicate about it.
