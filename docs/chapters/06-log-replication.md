# Chapter 6: Log Replication

## What This Chapter Covers

Log replication is how the leader keeps follower logs synchronized. This chapter explains the replication protocol in detail: how the leader tracks follower progress with `nextIndex` and `matchIndex`, what happens when replication fails, and the rules for advancing `commitIndex`.

This is where Raft's safety guarantees become concrete. The commit index only advances when a majority has replicated an entry. The leader only commits entries from its current term. These rules prevent committed entries from being lost, even across leader failures.

## Sections

### The Leader's Responsibility

What it means to be leader: own the log, replicate to followers, track what's committed. The leader's view of the cluster through `nextIndex` and `matchIndex`. Why the leader initializes `match_index[self]` to `len(log) - 1`.

### nextIndex and matchIndex

Two dictionaries, two purposes. `nextIndex[follower]` is the next entry to send—optimistic, decremented on failure. `matchIndex[follower]` is the highest entry known replicated—conservative, incremented on success. The interplay between them.

### The Heartbeat Flow

`handle_leader_heartbeat` sends `AppendEntryRequest` to all followers. How `create_append_entries_arguments` builds the request: entries from `nextIndex` onward, previous index/term, current commit index.

### Handling Append Entry Responses

`handle_append_entries_response` processes follower replies. On success: increment `nextIndex`, update `matchIndex`. On failure: decrement `nextIndex`, retry with earlier entries. Why failure means log inconsistency, not network failure.

### The Follower's Perspective

`handle_append_entries_request` from the follower's side. Validate term. Call `append_entries` on the log. Update own `commit_index` based on leader's value. Return success or failure.

### Advancing commitIndex

`update_indexes` and `get_index_metrics`. The median calculation: find the index replicated on a majority. The critical check: `log[potential_commit_index].term == current_term`. Why leaders don't commit entries from previous terms directly.

### The Figure 8 Problem

The Raft paper's Figure 8 shows why committing old-term entries is dangerous. A committed entry could be overwritten if the leader crashes before replicating it. The solution: only commit through current-term entries, which implicitly commit all preceding entries.

### Testing Replication Scenarios

The Figure 7 test cases in `test_raftstate.py`. Various log divergence scenarios (a through f) and how the protocol handles each. What these tests prove about correctness.

## Conclusion

Log replication is optimistic but self-correcting. The leader guesses where each follower's log ends (`nextIndex`), sends entries, and adjusts based on feedback. The commit rules ensure safety: only majority-replicated, current-term entries advance the commit index. These constraints—not clever algorithms—are what make Raft correct.
