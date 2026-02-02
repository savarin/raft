# Chapter 1: Introduction

## What This Chapter Covers

This chapter introduces the Raft consensus algorithm and sets the stage for the implementation that follows. You'll understand what problem Raft solves, why consensus is hard, and how this book approaches building a working implementation.

If you've read the Raft paper, this chapter provides context for how the implementation maps to the paper's concepts. If you haven't, it gives enough background to follow along—though you'll get more from this book if you've at least skimmed the paper first.

## Sections

### The Consensus Problem

What does it mean for distributed nodes to agree? The challenge of building reliable systems from unreliable components. Why we can't just use a database.

### Why Raft Exists

Paxos and its reputation for difficulty. The Raft paper's explicit goal of understandability. How Raft achieves consensus through leader election and log replication.

### The Raft Paper and Figure 2

A brief tour of the Raft paper's structure. Why Figure 2 is both essential and insufficient—it tells you *what* to implement but not *how*. The decisions left to the implementer.

### This Implementation's Approach

The architecture of this codebase: state machine logic separate from network I/O. Why pure Python, no frameworks. The design goal of testability.

### Running the Cluster

How to start a three-node cluster on your local machine. What the colored prompts mean. Sending commands and watching elections happen.

### Reading This Book

How the chapters are organized. What Part I, II, and III cover. How to read the code alongside the text.

## Conclusion

By the end of this chapter, you understand what Raft does at a high level, why this implementation is structured the way it is, and how to run the code yourself. You're ready to dive into the building blocks: logs, messages, and roles.
