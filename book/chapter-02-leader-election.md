# Chapter 2: Leader Election

*In which we explore how a leaderless cluster establishes authority, why randomness is essential to distributed systems, and what happens when old leaders refuse to step aside gracefully.*

---

## The Void of Leadership

In the steady state, a Raft cluster hums along quietly. The leader sends heartbeats, followers respond, logs replicate, commits advance. Everything works because everyone agrees on who's in charge.

Then the leader dies.

Perhaps the process crashed. Perhaps the server lost power. Perhaps a network switch failed, isolating the leader from the rest of the cluster. The cause doesn't matter—what matters is the consequence: followers stop receiving heartbeats.

For a brief moment, nothing happens. The followers don't know the leader is gone. They only know that time is passing without contact. One second. Two seconds. Three.

Then a timeout expires, and everything changes.

---

## The Election Timeout

Every Raft server maintains an **election timeout**—a duration after which, if no heartbeat has been received, the server assumes the leader has failed.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ELECTION TIMEOUT BEHAVIOR                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Follower receives heartbeat                                       │
│       → Reset election timeout                                      │
│       → Remain follower                                             │
│                                                                     │
│   Election timeout expires (no heartbeat received)                  │
│       → Convert to candidate                                        │
│       → Increment term                                              │
│       → Vote for self                                               │
│       → Send RequestVote to all other servers                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The implementation handles this in `raftserver.py`:

```python
TIMEOUT = 3  # seconds

def cycle(self) -> None:
    timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

    self.timer.cancel()
    self.timer = threading.Timer(timeout, self.timeout)
    self.timer.start()

    self.reset = True
```

Notice the asymmetry: leaders use `TIMEOUT` (3 seconds), while followers and candidates use `2 * TIMEOUT` (6 seconds). This ensures leaders send heartbeats faster than followers expect them, providing margin for network delays.

When the timeout fires without a heartbeat being received:

```python
def timeout(self) -> None:
    # Random timeout before starting elections.
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)

    if self.reset:
        message = raftstate.change_state_on_timeout(self.state)
        self.node.incoming.put(raftmessage.encode_message(message))

    self.cycle()
```

The `random.random() * TIMEOUT` is crucial—we'll explore why shortly.

---

## Becoming a Candidate

When a follower's election timeout expires, it doesn't immediately hold an election. Instead, it generates a `RoleChange` message that transitions it to the candidate state:

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
        # ...
```

This message is processed like any other, triggering the transition logic in `handle_role_change`:

```python
def handle_role_change(
    self,
    source: int,
    target: int,
    from_role: raftrole.Role,
    to_role: raftrole.Role,
) -> List[raftmessage.Message]:
    assert self.role == from_role

    match (from_role, to_role):
        case (raftrole.Role.FOLLOWER, raftrole.Role.CANDIDATE):
            self.change_role(from_role, to_role)
            return [
                raftmessage.RunElection(
                    self.identifier, self.identifier, self.create_followers_list()
                )
            ]
```

The transition from follower to candidate triggers several state changes, codified in `raftrole.py`:

```python
# timeout
case (Role.TIMER, Role.FOLLOWER):
    current_term = target_term + 1    # Increment term
    voted_for = Operation.INITIALIZE  # Vote for self
    role_change = (Role.FOLLOWER, Role.CANDIDATE)
```

When a server becomes a candidate:

1. **Term increments by one** — This is a new election epoch
2. **Votes for itself** — Every candidate votes for itself first
3. **Vote tracking initializes** — The `current_votes` dictionary is created
4. **RequestVote messages are sent** — To every other server in the cluster

---

## The RequestVote RPC

A candidate solicits votes by sending `RequestVoteRequest` messages to all other servers:

```python
def handle_candidate_solicitation(
    self,
    source: Optional[int] = None,
    target: Optional[int] = None,
    followers: Optional[List[int]] = None,
) -> List[raftmessage.Message]:
    """
    Candidate soliciting votes. Send RequestVoteRequest to all followers.
    """
    if self.role != raftrole.Role.CANDIDATE:
        raise Exception("Not able to solicit votes when not candidate.")

    followers = followers or self.create_followers_list()
    messages: List[raftmessage.Message] = []

    previous_term = self.log[-1].term if len(self.log) > 0 else -1

    for follower in followers:
        message = raftmessage.RequestVoteRequest(
            self.identifier,
            follower,
            self.current_term,
            len(self.log) - 1,    # last_log_index
            previous_term,         # last_log_term
        )
        messages.append(message)

    return messages
```

Each `RequestVoteRequest` contains:

| Field | Purpose |
|-------|---------|
| `current_term` | The candidate's term (new election epoch) |
| `last_log_index` | Index of candidate's last log entry |
| `last_log_term` | Term of candidate's last log entry |

The last two fields are critical for **safety**—they ensure that only candidates with complete logs can win elections.

---

## The Art of Granting Votes

When a server receives a `RequestVoteRequest`, it must decide: should I vote for this candidate?

The decision follows a careful sequence of checks:

```python
def handle_request_vote_request(
    self,
    source: int,
    target: int,
    current_term: int,
    last_log_index: int,
    last_log_term: int,
) -> List[raftmessage.Message]:
    # First: check if this message changes our state
    state_change = raftrole.enumerate_state_change(
        raftrole.Role.CANDIDATE, current_term, self.role, self.current_term
    )
    self.implement_state_change(state_change)

    # If not follower, reject immediately
    if self.role != raftrole.Role.FOLLOWER:
        return [
            raftmessage.RequestVoteResponse(
                target, source, False, self.current_term
            )
        ]

    # Check 1: Candidate must have term >= our term
    if current_term < self.current_term:
        success = False

    # Check 2: Candidate's log must be at least as long as ours
    elif last_log_index < len(self.log) - 1:
        success = False

    # Check 3: Candidate's last entry must have term >= our last entry's term
    elif len(self.log) > 0 and last_log_term < self.log[-1].term:
        success = False

    else:
        # Check 4: We haven't voted for someone else this term
        if self.voted_for is not None and self.voted_for != source:
            success = False
        else:
            if self.voted_for is None:
                self.voted_for = source
            success = True

    return [
        raftmessage.RequestVoteResponse(target, source, success, self.current_term)
    ]
```

Let's visualize this decision tree:

```
                    RequestVoteRequest received
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Am I a follower?    │
                    └─────────────────────┘
                         │           │
                        Yes          No
                         │           │
                         ▼           └──────────▶ REJECT
                    ┌─────────────────────┐
                    │ candidate_term >=   │
                    │ my_term?            │
                    └─────────────────────┘
                         │           │
                        Yes          No
                         │           │
                         ▼           └──────────▶ REJECT
                    ┌─────────────────────┐
                    │ candidate_log       │
                    │ at least as         │
                    │ up-to-date as mine? │
                    └─────────────────────┘
                         │           │
                        Yes          No
                         │           │
                         ▼           └──────────▶ REJECT
                    ┌─────────────────────┐
                    │ Have I already      │
                    │ voted for someone   │
                    │ else this term?     │
                    └─────────────────────┘
                         │           │
                        No          Yes
                         │           │
                         ▼           └──────────▶ REJECT
                      GRANT VOTE
```

---

## "At Least As Up-to-Date"

The most subtle part of vote granting is the "up-to-date" check. The Raft paper (§5.4.1) defines this precisely:

> Raft determines which of two logs is more up-to-date by comparing the index and term of the last entries in the logs. If the logs have last entries with different terms, then the log with the later term is more up-to-date. If the logs end with the same term, then whichever log is longer is more up-to-date.

In code:

```python
# Candidate's log must be at least as long as ours
elif last_log_index < len(self.log) - 1:
    success = False

# Candidate's last entry must have term >= our last entry's term
elif len(self.log) > 0 and last_log_term < self.log[-1].term:
    success = False
```

The order matters. We check the **term** of the last entry first (implicitly—if terms are equal, we proceed to length). Then we check log **length**.

Why this ordering? Consider two logs:

```
Server A (candidate):  [t1, t1, t1, t2, t2]  (length 5, last term 2)
Server B (voter):      [t1, t1, t1, t3]      (length 4, last term 3)
```

Server A has the longer log, but Server B has the more up-to-date log because its last entry has a higher term. Term 3 could only have been written by a leader elected after the term-2 leader, so Server B's log reflects more recent authority.

If we allowed Server A to win an election, it could overwrite Server B's term-3 entries with its term-2 entries—entries from a leader that had already been superseded. This would violate safety.

---

## Vote Tracking and Majority

A candidate tracks votes in a dictionary:

```python
self.current_votes: Optional[Dict[int, Optional[int]]] = None
```

When becoming a candidate, this is initialized with a self-vote:

```python
case state_change["current_votes"]:
    case raftrole.Operation.INITIALIZE:
        self.current_votes = {identifier: None for identifier in self.config}
        self.current_votes[self.identifier] = self.identifier
```

When a positive vote response arrives:

```python
def handle_request_vote_response(
    self,
    source: int,
    target: int,
    success: bool,
    current_term: int,
) -> List[raftmessage.Message]:
    # ... state change handling ...

    if self.role != raftrole.Role.CANDIDATE:
        return []

    if success:
        self.current_votes[source] = target  # Record the vote

        if self.has_won_election():
            # Transition to leader
            state_change = raftrole.enumerate_state_change(
                raftrole.Role.ELECTION_COMMISSION,
                self.current_term,
                self.role,
                self.current_term,
            )
            self.implement_state_change(state_change)

            # Immediately send heartbeats to assert leadership
            return [
                raftmessage.UpdateFollowers(
                    self.identifier, self.identifier, self.create_followers_list()
                )
            ]

    return []
```

The `has_won_election` check is simple:

```python
def count_majority(self) -> int:
    return 1 + len(self.config) // 2

def has_won_election(self) -> bool:
    return self.count_self_votes() >= self.count_majority()
```

For a 3-node cluster, majority is `1 + 3 // 2 = 2`. For 5 nodes, it's `1 + 5 // 2 = 3`.

---

## Anatomy of an Election

Let's trace through a complete election in a 3-server cluster where Server 1 is the leader and crashes:

```
Time    Server 1          Server 2          Server 3
─────────────────────────────────────────────────────────────
 0      LEADER            FOLLOWER          FOLLOWER
        (crash!)          term=5            term=5

 1      (dead)            waiting...        waiting...

 2      (dead)            waiting...        waiting...

 3      (dead)            waiting...        waiting...

 4      (dead)            waiting...        waiting...

 5      (dead)            waiting...        waiting...

 6      (dead)            timeout!          waiting...
                          → CANDIDATE       (random delay)
                          term=6
                          vote for self
                          send RequestVote
                              │
 7      (dead)                │──────────────▶ receive
                                              RequestVote
                                              term 6 > 5
                                              update term
                                              log up-to-date?
                                              yes → GRANT
                              ◀──────────────
                          receive vote
                          count: 2 (self + S3)
                          majority: 2
                          WON!
                          → LEADER
                          term=6
                          send heartbeat
                              │
 8      (dead)                │──────────────▶ receive
                                              heartbeat
                                              remain FOLLOWER
```

Server 2's election timeout expired first (due to randomization). It became a candidate, incremented its term to 6, voted for itself, and sent RequestVote to Servers 1 and 3. Server 1 is dead, so no response. Server 3 granted its vote (the log was up-to-date), giving Server 2 a majority (2 out of 3). Server 2 became leader and immediately sent heartbeats to establish authority.

---

## The Split Vote Problem

What happens if two servers' election timeouts expire simultaneously?

```
Time    Server 1          Server 2          Server 3
─────────────────────────────────────────────────────────────
 0      FOLLOWER          FOLLOWER          FOLLOWER
        term=5            term=5            term=5
        timeout!          timeout!

 1      → CANDIDATE       → CANDIDATE       waiting...
        term=6            term=6
        vote for self     vote for self
        send RequestVote  send RequestVote
            │                 │
 2          │─────────────────│──────────────▶ receive
            │◀────────────────│               RequestVote
            │                 │               from S1
            │                 │◀──────────────
            │                                 RequestVote
            │                                 from S2
            │
        receive RequestVote               Server 3 receives
        from S2                           BOTH requests
        I'm candidate                     simultaneously
        term 6 = 6
        → REJECT (not follower)
                                          Votes for S1
            ◀─────────────────────────────(first received)
                                              │
 3      receive vote                          │
        from S3                               │
        count: 2                              └──────────────▶
        majority: 2                       S2 gets rejection
        WON!                              from S3 (already
                                          voted for S1)
```

In this scenario, Server 1 won because Server 3's vote response reached it first. But consider if Server 3's responses had been delayed differently—Server 2 might have won instead.

Now consider the worst case:

```
Time    Server 1          Server 2          Server 3
─────────────────────────────────────────────────────────────
 0      CANDIDATE         CANDIDATE         FOLLOWER
        term=6            term=6            term=5
        vote: self        vote: self

        RequestVote ──────────────────────▶ receives S1's
                                           request first
                                           votes for S1
                    ◀────────────────────── vote for S1

        receives S3's vote
        count: 2 (self + S3)
        majority: 2
        ... but wait ...

                          RequestVote ────▶ receives S2's
                                           request
                                           already voted!
                    ◀───────────────────── reject

                          receives rejection
                          count: 1 (self only)
                          no majority
```

Server 1 wins. But what if the network delivered Server 2's request first?

```
        (alternative timeline)

        RequestVote ─────────────────────▶ receives S2's
                                          request first
                                          votes for S2
                    ◀───────────────────── vote for S2

                          receives vote
                          count: 2 (self + S3)
                          WON!

        RequestVote ─────────────────────▶ receives S1's
                                          request
                                          already voted!
                    ◀───────────────────── reject
```

Now Server 2 wins. The outcome depends on message ordering—but either outcome is *safe*. At most one candidate can receive a majority because each server votes only once per term.

The truly problematic case is when *no one* gets a majority:

```
    4-server cluster

    Server 1          Server 2          Server 3          Server 4
    CANDIDATE         CANDIDATE         FOLLOWER          FOLLOWER
    term=6            term=6            term=5            term=5

    vote: self        vote: self        votes for S1      votes for S2
    gets S3's vote    gets S4's vote

    count: 2          count: 2
    majority: 3       majority: 3
    NO WINNER         NO WINNER
```

This is a **split vote**. Neither candidate achieves majority. The election fails, and both servers remain candidates until their election timeouts expire, triggering a new election in a higher term.

---

## Randomization: The Cure for Split Votes

Split votes are resolved through **randomized election timeouts**. Look again at the timeout handler:

```python
def timeout(self) -> None:
    # Random timeout before starting elections.
    if self.state.role == raftrole.Role.FOLLOWER:
        time.sleep(random.random() * TIMEOUT)
    # ...
```

Each follower waits a random additional time (0 to TIMEOUT seconds) before becoming a candidate. This makes simultaneous candidacy unlikely.

```
                    Base timeout expires
                           │
                           ▼
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   Server 1: wait 0.3s, then become candidate           │
    │   Server 2: wait 2.1s, then become candidate           │
    │   Server 3: wait 1.7s, then become candidate           │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
                           │
                           ▼
              Server 1 becomes candidate first
              Sends RequestVote to others
              Others are still followers
              They grant votes
              Server 1 wins before others even start
```

The random delays create a "window of opportunity" for each server. The first server to start its election usually wins because the others haven't become candidates yet (and followers grant votes to the first qualified candidate they see).

If split votes do occur (the random delays were too close), the same randomization helps on retry:

```python
case raftrole.Role.CANDIDATE:
    state.current_term += 1  # Bump term
    return raftmessage.RunElection(
        state.identifier, state.identifier, state.create_followers_list()
    )
```

When a candidate's election timeout expires without winning, it increments its term and tries again. The randomization ensures that eventually, one candidate will get enough of a head start to win.

---

## The One-Vote-Per-Term Rule

A critical invariant: **each server votes for at most one candidate per term**.

This is enforced by the `voted_for` field:

```python
# Require vote not already cast to a different candidate.
if self.voted_for is not None and self.voted_for != source:
    success = False
else:
    if self.voted_for is None:
        self.voted_for = source
    success = True
```

When the term changes, `voted_for` is reset:

```python
if source_term > target_term:
    current_term = source_term
    voted_for = Operation.RESET_TO_NONE  # New term = can vote again
```

This guarantees that in any given term, at most one candidate can receive a majority. Two candidates receiving majorities would require at least one server to vote twice—impossible under this rule.

The implementation also handles **vote idempotence**: if a candidate resends its RequestVote (perhaps the first response was lost), a server that already voted for that candidate will vote again:

```python
if self.voted_for is not None and self.voted_for != source:
    success = False  # Voted for someone else
else:
    # Either haven't voted, or already voted for this candidate
    if self.voted_for is None:
        self.voted_for = source  # Record the vote
    success = True  # Grant (or re-grant) the vote
```

This idempotence is important for reliability—lost messages shouldn't prevent valid elections.

---

## When Leaders Discover They're Not Leaders

Consider a scenario where a leader is partitioned from the cluster:

```
    Initial state: Server 1 is leader, term 5

    ┌──────────────────────┐     ┌──────────────────────┐
    │   Partition A        │     │   Partition B        │
    │                      │     │                      │
    │   Server 1           │     │   Server 2           │
    │   LEADER             │ ╳ ╳ │   FOLLOWER           │
    │   term=5             │     │   term=5             │
    │                      │     │                      │
    │                      │     │   Server 3           │
    │                      │     │   FOLLOWER           │
    │                      │     │   term=5             │
    └──────────────────────┘     └──────────────────────┘

    Time passes...

    Partition A:                  Partition B:
    - S1 sends heartbeats        - S2, S3 stop receiving
    - No responses (isolated)      heartbeats
    - Eventually steps down      - Election timeout
      (no has_followers)         - S2 becomes candidate
                                 - S2 wins election
                                 - S2 is leader, term=6
```

The old leader (Server 1) detects isolation through the `has_followers` flag:

```python
case raftrole.Role.LEADER:
    assert state.has_followers is not None

    # If no response received from previous heartbeat, step down
    if not state.has_followers:
        return raftmessage.RoleChange(
            state.identifier,
            state.identifier,
            raftrole.Role.LEADER,
            raftrole.Role.FOLLOWER,
        )

    # Otherwise send another heartbeat
    state.has_followers = False
    return raftmessage.UpdateFollowers(...)
```

Each heartbeat cycle:
1. Leader sets `has_followers = False`
2. Leader sends heartbeats
3. When responses arrive, `has_followers` is set to `True`
4. On next timeout, if `has_followers` is still `False`, leader steps down

Now, when the partition heals:

```
    Partition heals, network reconnects

    Server 1               Server 2               Server 3
    FOLLOWER               LEADER                 FOLLOWER
    term=5                 term=6                 term=6

    ◀────────────────────── heartbeat ────────────────────▶
    receive heartbeat
    term 6 > 5
    update term to 6
    remain FOLLOWER
```

Server 1 receives a heartbeat from Server 2 with term 6. Since 6 > 5, Server 1 updates its term and remains a follower. The cluster has reconverged with Server 2 as the legitimate leader.

What if Server 1 had tried to become a candidate before receiving the heartbeat?

```
    Server 1               Server 2               Server 3
    CANDIDATE              LEADER                 FOLLOWER
    term=6                 term=6                 term=6
    (just became
     candidate)

    RequestVote ──────────────────────────────────────────▶
                           receive RequestVote
                           I'm leader, term=6
                           candidate term=6 (equal)
                           → remain LEADER
                           → REJECT
                ◀──────────────────────────────────────────
    receive rejection
    term=6
    remain CANDIDATE
    no majority possible
    ... eventually timeout ...
```

Server 1's candidacy fails because Server 2, as a leader with equal term, rejects the vote request. Server 1 remains a candidate until its timeout, at which point it might increment its term and try again—or receive a heartbeat from Server 2 and step down.

---

## Election Scenarios from the Test Suite

The test suite validates several election scenarios. Let's examine them:

### Scenario 1: Successful Vote Grant

```python
# From test_handle_vote_request

candidate_state.change_role(raftrole.Role.FOLLOWER, raftrole.Role.CANDIDATE)
request = candidate_state.handle_candidate_solicitation()
assert candidate_state.current_term == 7  # Incremented from 6
assert candidate_state.voted_for == 1     # Voted for self

# Follower with shorter log (Figure 7a) grants vote
response = follower_a_state.handle_message(request[0])
assert response[0].success  # Vote granted
```

The candidate's log (Figure 7c) is longer than the follower's (Figure 7a), so the up-to-date check passes.

### Scenario 2: Rejection Due to Longer Voter Log

```python
# Follower (Figure 7d) has longer log than candidate (Figure 7c)
response = follower_d_state.handle_message(request[1])
assert not response[0].success  # Vote rejected

# After removing entries to make logs equal length...
follower_d_state.log.pop()
follower_d_state.log.pop()
response = follower_d_state.handle_message(request[1])
assert response[0].success  # Now vote granted
```

The voter in Figure 7d has 12 entries; the candidate in Figure 7c has 11. The voter rejects because its log is more complete.

### Scenario 3: Rejection Due to Already Voted

```python
# First vote to candidate 1
response = follower_a_state.handle_message(request[0])
assert response[0].success

# Second candidate (different server) requests vote
response = follower_a_state.handle_request_vote_request(2, 1, 7, 10, 6)
assert not response[0].success  # Rejected: already voted for candidate 1
```

The one-vote-per-term rule in action.

### Scenario 4: Complete Election with Victory

```python
# From test_handle_vote_response

# Candidate starts with 1 vote (self)
candidate_state, request = init_raft_state(
    1, logs_by_identifier["c"], raftrole.Role.CANDIDATE, 7
)

# First vote response: rejection (follower has longer log)
response = follower_d_state.handle_message(request[0])
assert not response[0].success
candidate_state.handle_message(response[0])
assert candidate_state.role == raftrole.Role.CANDIDATE  # Still candidate

# Second vote response: granted (follower has shorter log)
response = follower_a_state.handle_message(request[1])
assert response[0].success
candidate_state.handle_message(response[0])
assert candidate_state.role == raftrole.Role.LEADER  # Won! (2 votes in 3-node cluster)
```

The candidate collects votes until reaching majority, then immediately transitions to leader.

---

## The Meta-Roles: TIMER and ELECTION_COMMISSION

The implementation uses "meta-roles" to model internal state transitions that aren't triggered by external messages:

```python
class Role(enum.Enum):
    LEADER = "LEADER"
    CANDIDATE = "CANDIDATE"
    FOLLOWER = "FOLLOWER"
    TIMER = "TIMER"
    ELECTION_COMMISSION = "ELECTION_COMMISSION"
    CONSTITUTION = "CONSTITUTION"
```

These aren't real server roles—they're conceptual sources of state changes:

| Meta-Role | Triggers Transition |
|-----------|---------------------|
| `TIMER` | Follower → Candidate (election timeout) |
| `ELECTION_COMMISSION` | Candidate → Leader (won election) |
| `CONSTITUTION` | Leader → Follower (no follower responses) |

This design allows all state transitions to flow through the same `enumerate_state_change` function:

```python
def change_role(
    self,
    from_role: raftrole.Role,
    to_role: raftrole.Role,
    current_term: Optional[int] = None,
) -> Tuple[raftrole.Role, raftrole.Role]:
    match from_role:
        case raftrole.Role.FOLLOWER:
            source_role = raftrole.Role.TIMER

        case raftrole.Role.CANDIDATE:
            source_role = raftrole.Role.ELECTION_COMMISSION

        case raftrole.Role.LEADER:
            source_role = raftrole.Role.CONSTITUTION

    state_change = raftrole.enumerate_state_change(
        source_role,
        current_term or self.current_term,
        from_role,
        current_term or self.current_term,
    )
    # ...
```

The metaphor is apt:
- A **timer** declares when an election should start
- An **election commission** certifies the winner
- A **constitution** defines when a leader must step down

---

## State Changes on Election Victory

When a candidate wins, several state variables must be initialized:

```python
case (Role.CANDIDATE, Role.LEADER):
    next_index = Operation.INITIALIZE    # Track where followers are
    match_index = Operation.INITIALIZE   # Track what's replicated
    commit_index = Operation.PASS        # Keep current value
    has_followers = Operation.INITIALIZE # Start tracking responses
    current_votes = Operation.PASS       # No longer needed, but harmless
```

The initialization of `next_index` is particularly important:

```python
case raftrole.Operation.INITIALIZE:
    self.next_index = {
        identifier: len(self.log) for identifier in self.config
    }
```

The new leader optimistically assumes all followers have the same log. The first heartbeat will test this assumption; if a follower's log doesn't match, `next_index` will be decremented and retry—but that's the topic of Chapter 3.

---

## What We've Learned

This chapter explored the complete lifecycle of a Raft election:

- **Election timeouts** detect leader failure by measuring silence
- **Candidates** increment their term, vote for themselves, and solicit votes
- **Vote granting** requires the candidate's log to be "at least as up-to-date"
- **Majority vote** is required to win—preventing split-brain
- **Split votes** are resolved through randomized timeouts
- **One vote per term** guarantees at most one winner per election
- **Partitioned leaders** discover their obsolescence through term comparison

The election mechanism is intentionally over-provisioned. Multiple safeguards prevent split-brain:

1. Majority requirement means two leaders would need overlapping voters
2. One-vote-per-term means no voter can be in both majorities
3. Term comparison means old leaders defer to new ones
4. Log up-to-dateness means incomplete logs can't win

Any one of these would suffice in many cases, but together they make the algorithm robust against a wide range of failure modes.

---

## Looking Ahead

Elections establish *who* leads. Chapter 3 explores *what* leaders do: the log replication mechanism that distributes commands to followers and decides when those commands are safe to execute.

We'll work through the famous "Figure 7" scenarios from the Raft paper—logs that have diverged due to various failure patterns—and trace how the implementation brings them back into consistency.

---

## Exercises

1. **Election Timing**: In the implementation, the election timeout is `2 * TIMEOUT` for followers and candidates, while leaders use `TIMEOUT` for heartbeats. What would happen if these were equal? What if the election timeout were *shorter* than the heartbeat interval?

2. **The Up-to-Date Check**: Consider this scenario:
   ```
   Server A log: [t1, t1, t2]
   Server B log: [t1, t1, t1, t1]
   ```
   If both become candidates simultaneously, which can win votes from the other? Trace through the `handle_request_vote_request` logic.

3. **Split Vote Recovery**: In a 5-node cluster, suppose two candidates each receive exactly 2 votes (their own plus one other), and the fifth server hasn't voted yet. What happens next? What if the fifth server is partitioned from both candidates?

4. **Term Inflation**: A server is partitioned from the cluster for an extended period. It repeatedly times out and increments its term: 5, 6, 7, ... 100. When the partition heals, what happens? Is this a problem?

5. **Hands-On**: Start a 3-node cluster. Identify the leader. Kill a follower. Does a new election occur? Why or why not? Now kill the leader. Observe the election. Restart both killed servers. What roles do they assume?

6. **Code Tracing**: In `handle_request_vote_response`, why does the implementation check `if self.role != raftrole.Role.CANDIDATE` after implementing the state change? What scenario does this guard against?

---

*The next chapter examines log replication—the mechanism by which leaders distribute commands and maintain consistency across the cluster.*
