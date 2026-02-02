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

# Quick Start Guide

## Running the Cluster

---

# Prerequisites

- Python 3.10 or higher (uses `match/case` syntax)
- No external dependencies required

```bash
# Check Python version
python --version
# Python 3.10.x or higher
```

---

# Start the Cluster

Open **four terminal windows**

**Terminal 1 — Server 1:**
```bash
python src/raftserver.py 1
```

**Terminal 2 — Server 2:**
```bash
python src/raftserver.py 2
```

**Terminal 3 — Server 3:**
```bash
python src/raftserver.py 3
```

**Terminal 4 — Client:**
```bash
python src/raftclient.py 0
```

---

# Server Prompt Colors

Servers display their role with colors:

| Color | Role |
|-------|------|
| Red | Follower |
| Yellow | Candidate |
| Green | Leader |

```
1 >     # Red - Follower
1 >     # Yellow - Candidate (briefly)
1 >     # Green - Leader!
```

---

# Client Commands

**Append entries to a server:**
```
0 > 1 append hello world
```
Sends "hello" and "world" as entries to server 1

**View all server states:**
```
0 > self
```
Displays state of all servers

---

# Example Session

```bash
# Start all servers, wait for election...

# On client:
0 > 1 append a b c
# (If server 1 is leader, entries are appended)

0 > self
# Shows all server states with their logs
```

---

# What You'll See

**Server terminals:**
```
1 > [received] AppendEntryResponse from 2
1 > [received] AppendEntryResponse from 3
```

**Client terminal:**
```
0 > self
Server 1: term=1, role=LEADER, log=[a, b, c]
Server 2: term=1, role=FOLLOWER, log=[a, b, c]
Server 3: term=1, role=FOLLOWER, log=[a, b, c]
```

---

# Testing Failures

Try stopping the leader (Ctrl+C)

1. Remaining servers will timeout
2. One becomes candidate
3. Requests votes
4. Becomes new leader

```
# Server 2 terminal (was follower, becomes leader)
2 >     # Red → Yellow → Green
```

---

# Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_raftstate.py

# Run with verbose output
pytest -v
```

---

# Network Configuration

Servers use localhost with port mapping:

```python
ADDRESS_BY_IDENTIFIER = {
    1: ("localhost", 7000),
    2: ("localhost", 8000),
    3: ("localhost", 9000),
}
```

Client uses port 6000

---

# Timeout Configuration

| Role | Timeout |
|------|---------|
| Leader | 3 seconds (heartbeat) |
| Follower | 6 seconds + random 0-3s |
| Candidate | 6 seconds + random 0-3s |

Randomization prevents split votes

---

# Key Observations

1. **Only one leader** at any time
2. **Logs converge** — all servers have same entries
3. **Failures handled** — new elections work
4. **Order preserved** — entries applied in order

---

# Learn More

**Original Raft Paper:**
"In Search of an Understandable Consensus Algorithm"
https://raft.github.io/raft.pdf

**Raft Visualization:**
https://thesecretlivesofdata.com/raft/

**David Beazley's Course:**
https://www.dabeaz.com/raft.html

---

# Thank You!

## Questions?
