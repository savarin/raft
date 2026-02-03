# Video Proposal: Raft Consensus Overview

## The One Thing

After watching this video, viewers will understand how Raft achieves distributed consensus through three simple rules: higher terms win, continuity checks prevent divergence, and majority quorums make decisions.

## Audience

- Software engineers familiar with distributed systems concepts
- Developers who have heard of Raft but haven't internalized how it works
- Recurse Center peers who appreciate depth over surface-level explanations

**Assumed knowledge:** Basic understanding of client-server architecture, what "replication" means, why distributed systems need coordination.

**Not assumed:** Prior knowledge of consensus algorithms, Paxos, or Raft specifics.

## Why Video?

This concept benefits from animation because:

1. **State transitions are temporal** — Follower → Candidate → Leader happens over time with specific triggers. Animation shows causality that diagrams can't.

2. **Log replication is spatial** — The "walking backward to find consistency" algorithm is fundamentally visual. Seeing logs align and diverge makes the elegance obvious.

3. **Concurrent events need choreography** — Multiple servers sending messages, timeouts firing, votes being counted — animation can show parallelism that sequential text obscures.

4. **Term numbers as logical clocks** — Watching messages get rejected because of stale terms makes the concept visceral in a way static diagrams don't.

A static diagram shows *what* Raft does. Animation shows *why* it works.

## Duration

**Target: 3 minutes (180 seconds)**

This is a concept-with-context video: introduce the problem, show the three core mechanisms (election, replication, safety), and connect them to the underlying principles.

## Call to Action

After watching, viewers should:

1. Read the Raft paper's Figure 2 (state machine summary) — they'll now understand every line
2. Explore this codebase's `raftstate.py` to see how the state machine translates to code
3. Try breaking the protocol mentally: "What if two candidates get equal votes?" — and realize the protocol handles it

## Scope Boundaries

**In scope:**
- Leader election mechanism
- Log replication basics
- How terms prevent split-brain
- Why majority quorums matter

**Out of scope:**
- Log compaction / snapshotting
- Cluster membership changes
- Performance optimizations
- Comparison with Paxos

## Visual Style

- Three colored nodes (blue, green, orange) representing servers
- Arrows for message flow
- Log entries as stacked rectangles
- Term numbers prominently displayed
- Minimal text on screen — let animation carry meaning
