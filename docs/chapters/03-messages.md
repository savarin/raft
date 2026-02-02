# Chapter 3: Messages

## What This Chapter Covers

Raft servers communicate through a defined set of messages. This chapter catalogs those message types, explains what each one does, and shows how they map to the RPCs described in the Raft paper. You'll also see how messages are serialized for network transmission using Bencode.

Messages are the vocabulary of Raft. After this chapter, you'll recognize an `AppendEntryRequest` or `RequestVoteResponse` and know its purpose. The state machine chapter (Chapter 5) shows how these messages are processed; this chapter focuses on what they contain.

## Sections

### The Message Hierarchy

The base `Message` class: source and target. Why every message carries both—the sender's identity matters for processing the response. Subclasses add type-specific fields.

### AppendEntries Messages

`AppendEntryRequest`: the leader's tool for replication and heartbeats. Its fields map directly to Figure 2: term, previous index/term, entries, and leader's commit index. `AppendEntryResponse`: success or failure, and the term for the leader to update itself.

### RequestVote Messages

`RequestVoteRequest`: a candidate soliciting votes. The fields that let voters decide: term, and information about the candidate's log (last index and last term). `RequestVoteResponse`: vote granted or denied.

### Internal Messages

Messages that don't cross the network: `ClientLogAppend` (from the client), `UpdateFollowers` (leader's heartbeat trigger), `RunElection` (candidate's vote solicitation trigger), `RoleChange` (timeout-driven transitions). These are internal events wrapped as messages for uniform handling.

### The MessageType Enum

How the implementation tags messages for serialization. The mapping between Python classes and string identifiers.

### Bencode Serialization

Why Bencode: simple, unambiguous, no external dependencies. The encoding rules for integers, strings, lists, and dictionaries. The `encode_message` and `decode_message` functions. Why `LogEntry` objects need special handling.

### Testing Serialization

The round-trip test pattern: encode, decode, compare. Why this matters—serialization bugs cause silent data corruption.

## Conclusion

Nine message types, each with a specific role. External messages (`AppendEntry*`, `RequestVote*`) cross the network between servers. Internal messages (`UpdateFollowers`, `RunElection`, `RoleChange`) represent timer-driven events. Together they form the complete vocabulary of server communication. The state machine consumes these messages and produces responses—that's next.
