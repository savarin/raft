---
marp: true
theme: default
paginate: true
backgroundColor: #1a1a2e
color: #eaeaea
style: |
  h1, h2, h3 {
    color: #00d4ff;
  }
  code {
    background-color: #16213e;
  }
  pre {
    background-color: #16213e;
  }
---

# How It Works

## Leader Election & Log Replication

---

# Starting State

All servers start as **followers**

```
Server 1 (Follower)     Server 2 (Follower)     Server 3 (Follower)
+------------------+    +------------------+    +------------------+
| term: 0          |    | term: 0          |    | term: 0          |
| voted_for: None  |    | voted_for: None  |    | voted_for: None  |
| log: []          |    | log: []          |    | log: []          |
+------------------+    +------------------+    +------------------+
```

Each follower starts an **election timer** (random 3-6 seconds)

---

# Election Trigger

When election timer expires, follower becomes **candidate**

```python
def change_state_on_timeout(self) -> StateChange:
    if self.role == Role.FOLLOWER:
        # Become candidate
        return enumerate_state_change(
            origin_role=self.role,
            target_role=Role.CANDIDATE,
            new_term=self.current_term + 1,
        )
```

---

# Requesting Votes

Candidate sends `RequestVoteRequest` to all servers

```
          +------------------+
          | Server 1         |
          | CANDIDATE        |
          | term: 1          |
          +------------------+
                  |
    RequestVote   |   RequestVote
    +-------------+-------------+
    |                           |
    v                           v
+------------------+    +------------------+
| Server 2         |    | Server 3         |
| FOLLOWER         |    | FOLLOWER         |
+------------------+    +------------------+
```

---

# Vote Decision

Followers grant vote if:

1. Candidate's term >= follower's term
2. Follower hasn't voted in this term
3. Candidate's log is at least as up-to-date

```python
def handle_request_vote_request(self, message):
    vote_granted = (
        message.term >= self.current_term
        and self.voted_for in (None, message.candidate_id)
        and self.is_candidate_up_to_date(message)
    )
```

---

# Winning the Election

Candidate receiving **majority** of votes becomes leader

```python
def handle_request_vote_response(self, message):
    if message.vote_granted:
        self.current_votes.add(message.source)

    if len(self.current_votes) > len(PEERS) // 2:
        # Become leader!
        return self.implement_state_change(
            target_role=Role.LEADER
        )
```

With 3 servers, need 2 votes (including self)

---

# New Leader

Leader immediately:
1. Initializes `next_index` for each follower
2. Initializes `match_index` for each follower
3. Sends heartbeat to establish authority

```python
# Leader initialization
next_index = {peer: len(self.log) + 1 for peer in peers}
match_index = {peer: 0 for peer in peers}
```

---

# Client Request

Client sends `ClientLogAppend` to leader

```
+--------+                    +------------------+
| Client | --- append "x" --> | Leader (Server 1)|
+--------+                    +------------------+
                                      |
                              append to local log
                                      |
                              ack to client
```

Leader appends to log, immediately acknowledges client

---

# Log Replication

Leader sends `AppendEntryRequest` to followers

```
+------------------+
| Leader (S1)      |
| log: [x]         |
+------------------+
        |
        | AppendEntryRequest
        | entries: [x]
        | prev_log_index: 0
        | prev_log_term: 0
        +--------+--------+
        |                 |
        v                 v
+------------------+  +------------------+
| Follower (S2)    |  | Follower (S3)    |
| log: []          |  | log: []          |
+------------------+  +------------------+
```

---

# Follower Response

Follower checks log consistency and appends

```python
def handle_append_entries_request(self, message):
    # Check previous entry matches
    if not self.log_matches(
        message.prev_log_index,
        message.prev_log_term
    ):
        return AppendEntryResponse(success=False)

    # Append new entries
    self.log = append_entries(self.log, ...)
    return AppendEntryResponse(success=True)
```

---

# Tracking Replication

Leader tracks progress with `match_index`

```python
def handle_append_entries_response(self, message):
    if message.success:
        self.match_index[source] = message.match_index
        self.next_index[source] = message.match_index + 1
    else:
        # Decrement and retry
        self.next_index[source] -= 1
```

---

# Committing Entries

Entry committed when replicated on majority

```python
def update_commit_index(self):
    for n in range(self.commit_index + 1, len(self.log) + 1):
        replicated_on = sum(
            1 for peer in peers
            if self.match_index[peer] >= n
        ) + 1  # +1 for leader

        if replicated_on > len(peers) // 2:
            self.commit_index = n
```

---

# Heartbeat Mechanism

Leader sends periodic heartbeats (every 3 seconds)

```python
# Empty AppendEntryRequest = heartbeat
AppendEntryRequest(
    term=self.current_term,
    leader_id=self.identifier,
    prev_log_index=...,
    prev_log_term=...,
    entries=[],  # Empty!
    leader_commit=self.commit_index,
)
```

Prevents followers from starting elections

---

# Handling Failures

**Follower crashes:**
- Leader keeps retrying AppendEntryRequest
- Eventually follower recovers and syncs

**Leader crashes:**
- Followers time out, start election
- New leader elected
- Committed entries guaranteed to exist

---

# Log Conflict Resolution

When follower's log conflicts with leader's:

```
Leader log:   [1:a] [1:b] [2:c] [2:d]
Follower log: [1:a] [1:b] [1:x] [1:y]  <- conflict!
```

Leader decrements `next_index` and retries:

```python
if not success:
    self.next_index[follower] -= 1
    # Retry with earlier prev_log_index
```

Eventually finds matching point, overwrites conflicts

---

# Safety Guarantee

**Committed entries are never lost**

```
Before crash:    [a] [b] [c*]   * = committed
                      ^
                 majority have c

After election:  New leader must have [a] [b] [c]
                 (can only win with up-to-date log)
```

---

# Next Up

Running the cluster...
