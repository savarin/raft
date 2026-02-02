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
  a {
    color: #00d4ff;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
---

# Raft Overview

## The Three Pillars of Consensus

---

# The Three Server Roles

Every server is in one of three states:

| Role | Description |
|------|-------------|
| **Follower** | Passive, only responds to requests |
| **Candidate** | Actively seeking votes for leadership |
| **Leader** | Handles all client requests, replicates log |

---

# Role Transitions

```
                    times out,
                    starts election
        +-------+                  +----------+
        |       | ---------------> |          |
        |Follower|                 |Candidate |
        |       | <--------------- |          |
        +-------+   discovers      +----------+
            ^       leader or           |
            |       higher term         | receives majority
            |                           | of votes
            |       discovers           v
            |       higher term    +--------+
            +--------------------  | Leader |
                                   +--------+
```

---

# Terms: Logical Time

Raft divides time into **terms**

- Terms are numbered with consecutive integers
- Each term begins with an election
- At most one leader per term
- Terms act as a logical clock

```
     Term 1     Term 2     Term 3     Term 4     Term 5
   +--------+ +--------+ +--------+ +--------+ +--------+
   |election| |election| |election| |election| |election|
   |  s1    | |  s2    | | split  | |  s3    | |  s1    |
   | leader | | leader | |  vote  | | leader | | leader |
   +--------+ +--------+ +--------+ +--------+ +--------+
```

---

# The Replicated Log

Each server maintains a log of commands

```
   index:   1     2     3     4     5     6
         +-----+-----+-----+-----+-----+-----+
 Server1 | x←3 | y←1 | y←9 | x←2 | x←0 | y←7 |  LEADER
         +-----+-----+-----+-----+-----+-----+
           t1    t1    t1    t2    t3    t3

         +-----+-----+-----+-----+-----+-----+
 Server2 | x←3 | y←1 | y←9 | x←2 | x←0 | y←7 |  FOLLOWER
         +-----+-----+-----+-----+-----+-----+
           t1    t1    t1    t2    t3    t3

         +-----+-----+-----+-----+-----+
 Server3 | x←3 | y←1 | y←9 | x←2 | x←0 |       FOLLOWER
         +-----+-----+-----+-----+-----+
           t1    t1    t1    t2    t3
```

Each entry has: **index**, **term**, and **command**

---

# Key Safety Properties

**Election Safety**
At most one leader per term

**Leader Append-Only**
Leader never overwrites or deletes entries

**Log Matching**
If two logs have same index and term, they're identical

**Leader Completeness**
Committed entries will be present in future leaders

**State Machine Safety**
All servers apply same commands in same order

---

# Two Core RPCs

## AppendEntries
- Sent by leader to followers
- Replicates log entries
- Also used as heartbeat (empty entries)

## RequestVote
- Sent by candidates during elections
- Requests vote from each server
- Server grants vote if candidate's log is up-to-date

---

# Committed vs Applied

**Committed**: Entry is safely replicated on majority

**Applied**: Entry has been executed by state machine

```
Log:        [1] [2] [3] [4] [5] [6]
                    ^         ^
                    |         |
             last_applied   commit_index
```

Only committed entries are safe to apply

---

# Next Up

The codebase architecture...
