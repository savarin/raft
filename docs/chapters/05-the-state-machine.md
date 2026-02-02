# Chapter 5: The State Machine

## What This Chapter Covers

`RaftState` is the heart of this implementation. It holds all server state—log, term, role, indexes—and processes messages through handler methods. This chapter examines the class structure, the state it maintains, and the message dispatch pattern that routes each message type to its handler.

This is where Parts I and II connect. The log (Chapter 2) becomes `self.log`. The messages (Chapter 3) flow through `handle_message`. The role transitions (Chapter 4) happen via `implement_state_change`. Understanding `RaftState` means understanding how the pieces compose.

## Sections

### The `RaftState` Class

The class definition and `__post_init__`. Every attribute explained: log, role, current_term, next_index, match_index, commit_index, voted_for, current_votes, has_followers. Which attributes exist for all servers; which only for leaders or candidates.

### Persistent vs. Volatile State

The Raft paper distinguishes persistent state (survives restarts) from volatile state (lost on crash). This implementation doesn't persist state—it's all in memory. What you'd need to add for durability and why it's omitted here.

### The `handle_message` Dispatcher

Pattern matching on message types. Each case delegates to a handler method. Why this structure: clear routing, each handler has single responsibility, easy to trace which code processes which message.

### Implementing State Changes

The `implement_state_change` method. How it reads the `StateChange` dict from `raftrole` and applies updates. The special handling for different `Operation` values. Why commit_index resets to -1 instead of None.

### Helper Methods

`count_majority`, `create_followers_list`, and other utilities. Small functions that appear in multiple handlers. Why they're methods rather than module-level functions.

### The Handler Method Pattern

Every handler takes message fields as keyword arguments (via `**vars(message)`). Every handler returns a list of response messages (possibly empty). This uniform interface simplifies the dispatch loop.

### Testing RaftState

How to test state machine logic without network code. Create a `RaftState`, feed it messages, assert on the resulting state and responses. The tests in `test_raftstate.py` demonstrate this pattern.

## Conclusion

`RaftState` is 650 lines of code, but its structure is regular. State attributes at the top. Handlers grouped by role (client, leader, candidate). Each handler follows the same pattern: evaluate state change, update state, return responses. The next two chapters dive into specific handlers—log replication and elections—but the pattern remains the same.
