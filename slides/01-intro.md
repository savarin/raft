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
---

# Raft Consensus Algorithm

## A Python Implementation

---

# What is This Project?

A **complete implementation** of the Raft distributed consensus algorithm in Python

- Built from first principles
- Based on the original Raft paper
- Implements a 3-server cluster
- Pure Python standard library (no external dependencies)

---

# Why Raft?

Raft is designed to be **understandable**

- Equivalent to Paxos in fault-tolerance and performance
- Decomposed into independent subproblems
- Cleanly addresses all pieces needed for practical systems

> "In Search of an Understandable Consensus Algorithm"
> — Diego Ongaro and John Ousterhout, Stanford University

---

# What Does Consensus Mean?

Multiple servers agreeing on shared state

**The challenge:** Servers can fail, messages can be lost

**The goal:** Make a collection of machines work as a coherent group

- Even if some servers fail
- Even if network partitions occur
- As long as a **majority** survives

---

# Project Origin

Completed as part of **David Beazley's Rafting Trip** course

- Hands-on implementation from scratch
- Deep understanding of distributed systems
- https://www.dabeaz.com/raft.html

---

# Key Features Implemented

- **Leader Election** — Automatically elect a leader through voting
- **Log Replication** — Replicate entries across all servers
- **Safety** — Maintain consistency even during failures
- **Client Interface** — Handle client requests for log appends

---

# Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Networking | TCP Sockets |
| Concurrency | Threading |
| Serialization | Bencode |
| Testing | Pytest |

**Zero external dependencies**

---

# Next Up

Understanding the Raft algorithm itself...
