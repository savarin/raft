# Chapter 4: Roles and State Transitions

## What This Chapter Covers

A Raft server is always in one of three roles: Follower, Candidate, or Leader. This chapter explains what each role does, when servers transition between roles, and how the implementation encodes these rules. You'll meet the `Role` enum and the `enumerate_state_change` function that governs transitions.

Roles are simpler than they might appear. Followers wait. Candidates seek votes. Leaders replicate logs. The complexity is in the transitions—knowing when to change roles and what state to reset when you do.

## Sections

### The Three Roles

**Follower**: the default state. Followers accept log entries from the leader, grant votes to candidates, and wait. If they don't hear from a leader, they become candidates.

**Candidate**: a transitional state. Candidates increment their term, vote for themselves, and request votes from others. If they win, they become leader. If they hear from a new leader, they become followers.

**Leader**: the active state. Leaders send heartbeats, replicate log entries, and track what's been committed. Only one leader per term. If they lose contact with followers, they step down.

### Terms

The logical clock of Raft. Terms increase monotonically. Each term has at most one leader. Why higher terms always win—and what "winning" means for state transitions.

### The State Change Rules

The rules from Figure 2, translated to code. "If RPC contains term T > currentTerm, convert to follower." The complete enumeration of (source_role, target_role) pairs and what happens for each.

### Pseudo-Roles: Timer, Election Commission, Constitution

The implementation uses special roles to represent internal events. `TIMER` triggers follower-to-candidate transitions. `ELECTION_COMMISSION` signals a candidate has won. `CONSTITUTION` tells a leader to step down. These aren't real roles—they're markers that let the state change logic distinguish external RPCs from internal events.

### The `StateChange` TypedDict

What state needs updating on transitions: role, term, indexes, voted_for, current_votes. The `Operation` enum: PASS, RESET_TO_NONE, INITIALIZE. How `evaluate_operations` determines which attributes change.

### The `enumerate_state_change` Function

The central dispatch logic. Given source role/term and target role/term, compute the complete state change. Why this is a separate module—it's pure logic, no side effects, easy to test.

### Visual: The State Machine Diagram

A diagram showing the three roles and the transitions between them, labeled with their triggers (timeout, vote majority, higher term, etc.).

## Conclusion

Three roles, a handful of transitions, and a set of attributes that reset on each transition. The `raftrole` module encodes these rules as pure functions—given the current state and an event, compute the new state. This separation keeps the logic testable and the state machine (Chapter 5) focused on message handling rather than transition mechanics.
