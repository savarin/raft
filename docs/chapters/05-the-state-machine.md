# Chapter 5: The State Machine

`RaftState` is the heart of this implementation. It holds all server state—log, term, role, indexes—and processes messages through handler methods. This chapter examines the class structure, the state it maintains, and the message dispatch pattern that routes each message type to its handler.

This is where Parts I and II connect. The log (Chapter 2) becomes `self.log`. The messages (Chapter 3) flow through `handle_message`. The role transitions (Chapter 4) happen via `implement_state_change`. Understanding `RaftState` means understanding how the pieces compose.

## The RaftState Class

The class uses a dataclass with a single parameter—the server identifier:

```python
@dataclasses.dataclass
class RaftState:
    identifier: int

    def __post_init__(self) -> None:
        self.log: List[raftlog.LogEntry] = []
        self.role: raftrole.Role = raftrole.Role.FOLLOWER
        self.current_term: int = -1
        self.next_index: Optional[Dict[int, int]] = None
        self.match_index: Optional[Dict[int, Optional[int]]] = None
        self.commit_index: int = -1
        self.has_followers: Optional[bool] = None
        self.voted_for: Optional[int] = None
        self.current_votes: Optional[Dict[int, Optional[int]]] = None
        self.config: Dict[int, Tuple[str, int]] = raftconfig.ADDRESS_BY_IDENTIFIER
        self.experimental_mode: bool = False
```

Let's understand each attribute:

**All servers have:**

- **log**: The replicated log. A list of `LogEntry` objects.
- **role**: Current role—FOLLOWER, CANDIDATE, or LEADER.
- **current_term**: The latest term this server has seen. Starts at -1 (no term yet).
- **commit_index**: Index of the highest log entry known to be committed. Starts at -1 (nothing committed).
- **voted_for**: The candidate this server voted for in the current term. None if no vote cast.

**Leaders additionally use:**

- **next_index**: For each server, the next log index to send. Dictionary mapping server ID to index.
- **match_index**: For each server, the highest log index known to be replicated. Dictionary mapping server ID to index (or None if unknown).
- **has_followers**: Whether any follower has responded since the last heartbeat. Used to detect if the leader is isolated.

**Candidates additionally use:**

- **current_votes**: Tracks votes received. Dictionary mapping server ID to the candidate they voted for.

**Configuration:**

- **config**: Server addresses, from `raftconfig`.
- **experimental_mode**: A flag for testing. When true, allows committing entries from previous terms (which violates Raft's safety guarantee but simplifies some tests).

## Persistent vs. Volatile State

The Raft paper distinguishes persistent state (must survive restarts) from volatile state (can be lost):

**Persistent:**
- currentTerm
- votedFor
- log[]

**Volatile (all servers):**
- commitIndex
- lastApplied

**Volatile (leaders):**
- nextIndex[]
- matchIndex[]

This implementation doesn't persist anything—all state is in memory. If a server restarts, it loses everything. In a production implementation, you'd write the persistent state to disk before responding to any RPC.

The distinction still matters conceptually. If you were adding persistence, you'd know exactly which attributes need it.

## The handle_message Dispatcher

Every message flows through `handle_message`:

```python
def handle_message(self, message: raftmessage.Message) -> List[raftmessage.Message]:
    match message:
        case raftmessage.ClientLogAppend():
            return self.handle_client_log_append(**vars(message))

        case raftmessage.UpdateFollowers():
            return self.handle_leader_heartbeat(**vars(message))

        case raftmessage.AppendEntryRequest():
            return self.handle_append_entries_request(**vars(message))

        case raftmessage.AppendEntryResponse():
            return self.handle_append_entries_response(**vars(message))

        case raftmessage.RunElection():
            return self.handle_candidate_solicitation(**vars(message))

        case raftmessage.RequestVoteRequest():
            return self.handle_request_vote_request(**vars(message))

        case raftmessage.RequestVoteResponse():
            return self.handle_request_vote_response(**vars(message))

        case raftmessage.RoleChange():
            return self.handle_role_change(**vars(message))

        case raftmessage.Text():
            return self.handle_text(**vars(message))
```

The pattern match routes each message type to its handler. The `**vars(message)` idiom unpacks the message's fields as keyword arguments—so `handle_append_entries_request` receives `source`, `target`, `current_term`, etc. directly.

Each handler returns a list of messages to send in response. The list may be empty (no response needed), contain one message (typical for request/response), or contain multiple messages (leader sending to all followers).

## Implementing State Changes

When a handler needs to change state based on term comparison, it follows this pattern:

```python
def handle_append_entries_request(
    self,
    source: int,
    target: int,
    current_term: int,
    previous_index: int,
    previous_term: int,
    entries: List[raftlog.LogEntry],
    commit_index: int,
) -> List[raftmessage.Message]:

    # Compute what should change
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.LEADER, current_term, self.role, self.current_term
    )

    # Apply the changes
    self.implement_state_change(state_change)

    # Continue with handler logic...
```

The `enumerate_state_change` function (from Chapter 4) computes what should change: role, term, and which attributes to reset. The `implement_state_change` method applies those changes:

```python
def implement_state_change(self, state_change: raftrole.StateChange) -> None:
    if state_change["role_change"] is not None:
        assert state_change["role_change"][0] == self.role
        self.role = state_change["role_change"][1]

    self.current_term = state_change["current_term"]

    match state_change["next_index"]:
        case raftrole.Operation.RESET_TO_NONE:
            self.next_index = None
        case raftrole.Operation.INITIALIZE:
            self.next_index = {
                identifier: len(self.log) for identifier in self.config
            }

    # Similar handling for match_index, commit_index, has_followers,
    # voted_for, current_votes...
```

Note the initialization logic. When a candidate becomes leader, `next_index` is initialized to `len(self.log)` for all servers—optimistically assuming all followers are caught up. The leader will discover the actual state through AppendEntries responses.

For `match_index`, the leader initializes its own entry to `len(self.log) - 1` (it knows its own log is replicated on itself) but sets other servers to `None` (unknown until they respond).

## Helper Methods

Several helper methods appear across handlers:

```python
def count_majority(self) -> int:
    return 1 + len(self.config) // 2
```

For a 3-node cluster, majority is 2. For 5 nodes, majority is 3. The formula `1 + n // 2` works for any cluster size.

```python
def create_followers_list(self) -> List[int]:
    followers = list(self.config.keys())
    followers.remove(self.identifier)
    return followers
```

Returns all server IDs except the current server. Used when the leader needs to send messages to all followers.

## The Handler Pattern

Every handler follows the same structure:

1. **Compute state change**: Call `enumerate_state_change` with the message's term and role
2. **Apply state change**: Call `implement_state_change`
3. **Check current role**: If the state change caused a role change, early-return with appropriate response
4. **Process the message**: Role-specific logic
5. **Return response messages**: A list of messages to send

For example, `handle_append_entries_request`:

```python
def handle_append_entries_request(self, ...):
    # 1-2: Compute and apply state change
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.LEADER, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # 3: Check role - only followers process append entries
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.AppendEntryResponse(
                target, source, self.current_term, False, len(entries)
            )
        ]

    # 4: Process - append to log
    success = raftlog.append_entries(
        self.log, previous_index, previous_term, entries
    )

    # Update commit index based on leader's value
    if commit_index > self.commit_index:
        self.commit_index = min(commit_index, len(self.log) - 1)

    # 5: Return response
    return [
        raftmessage.AppendEntryResponse(
            target, source, self.current_term, success, len(entries)
        )
    ]
```

The pattern makes handlers predictable. You always know: check terms first, then check roles, then do the work, then respond.

## Timeout Handling

Timeouts don't arrive as network messages, but the implementation converts them to messages for uniform handling:

```python
def change_state_on_timeout(state: RaftState) -> raftmessage.Message:
    match state.role:
        case raftrole.Role.FOLLOWER:
            return raftmessage.RoleChange(
                state.identifier,
                state.identifier,
                raftrole.Role.FOLLOWER,
                raftrole.Role.CANDIDATE,
            )

        case raftrole.Role.CANDIDATE:
            state.current_term += 1
            return raftmessage.RunElection(
                state.identifier, state.identifier, state.create_followers_list()
            )

        case raftrole.Role.LEADER:
            if not state.has_followers:
                return raftmessage.RoleChange(
                    state.identifier,
                    state.identifier,
                    raftrole.Role.LEADER,
                    raftrole.Role.FOLLOWER,
                )

            state.has_followers = False
            return raftmessage.UpdateFollowers(
                state.identifier, state.identifier, state.create_followers_list()
            )
```

This function is called by `RaftServer` when the timer fires. It returns a message that then flows through `handle_message` like any other.

- **Follower timeout**: Generate `RoleChange` to become candidate
- **Candidate timeout**: Increment term, generate `RunElection` to request votes again
- **Leader timeout**: If no responses since last heartbeat, step down. Otherwise, generate `UpdateFollowers` for another heartbeat round and reset the flag.

The `has_followers` flag prevents a partitioned leader from staying leader forever. Each heartbeat sets it to `False`; responses set it back to `True`. If a timeout fires with the flag still `False`, the leader steps down.

## Testing RaftState

The beauty of this design is testability. You can test the algorithm without networks, threads, or timers:

```python
def test_append_entries():
    state = RaftState(1)
    state.role = Role.FOLLOWER
    state.current_term = 5

    # Simulate receiving an AppendEntryRequest
    responses = state.handle_message(
        AppendEntryRequest(
            source=2,
            target=1,
            current_term=5,
            previous_index=-1,
            previous_term=-1,
            entries=[LogEntry(5, "x")],
            commit_index=-1,
        )
    )

    # Verify the response
    assert len(responses) == 1
    assert responses[0].success == True

    # Verify state changed
    assert len(state.log) == 1
    assert state.log[0].item == "x"
```

Create a state, call handlers with constructed messages, verify the results. No mocking required. The tests in `test_raftstate.py` use this pattern extensively.

## Conclusion

`RaftState` is about 650 lines, but its structure is regular:

- State attributes at the top
- Helper methods for common calculations
- Handler methods grouped by role (client, leader, candidate, general)
- Each handler follows the same pattern: state change, role check, process, respond

The separation from network concerns is key. `RaftState` doesn't know about sockets or threads—it just processes messages and returns responses. The runtime (Chapter 8) handles the actual sending and receiving.

The next two chapters dive into specific handlers. Chapter 6 covers log replication: how `handle_leader_heartbeat` and `handle_append_entries_response` keep follower logs synchronized. Chapter 7 covers elections: how `handle_candidate_solicitation` and `handle_request_vote_request` elect new leaders.
