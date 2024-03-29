"""
Layer around the core append_entries operation to keep state of the log and
handle events.


State section in Figure 2 of Raft paper (minor divergence from 1-indexing in
paper vs 0-indexing implementation):

Persistent state on all servers:
currentTerm     latest term server has seen (initialized to 0 on first boot,
                increases monotonically)
votedFor        candidateId that received vote in current term (or null if none)
log[]           log entries; each entry contains command for state machine, and
                term when entry was received by leader (first index is 1)

Volatile state on all servers:
commitIndex     index of highest log entry known to be committed (initialized to
                0, increases monotonically)
lastApplied     index of highest log entry applied to state machine (initialized
                to 0, increases monotonically)

Volatile state on leaders:
nextIndex[]     for each server, index of the next log entry to send to that
                server (initialized to leader last log index + 1)
matchIndex[]    for each server, index of highest log entry known to be
                replicated on server (initialized to 0, increases monotonically)


AppendEntries RPCs section in Figure 2 of Raft paper:

Receiver implementation:
 1. Reply false if term < currentTerm (§5.1)
 5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, index of
    last new entry)


RequestVote RPCs section in Figure 2 of Raft paper:

Receiver implementation:
 1. Reply false if term < currentTerm (§5.1)
 2. If votedFor is null or candidateId, and candidate’s log is at least as
    up-to-date as receiver’s log, grant vote (§5.2, §5.4)


Rules for Servers section in Figure 2 of Raft paper:

Candidates (§5.2):
- If election timeout elapses: start new election

Leaders:
- Upon election: send initial empty AppendEntries RPCs (heartbeat) to each
  server; repeat during idle periods to prevent election timeouts (§5.2)
- If last log index ≥ nextIndex for a follower: send AppendEntries RPC with log
  entries starting at nextIndex
  - If successful: update nextIndex and matchIndex for follower (§5.3)
  - If AppendEntries fails because of log inconsistency: decrement nextIndex and
    retry (§5.3)
- If there exists an N such that N > commitIndex, a majority of matchIndex[i] ≥
  N, and log[N].term == currentTerm: set commitIndex = N (§5.3, §5.4).
"""
from typing import Dict, List, Optional, Tuple
import dataclasses

import raftconfig
import raftlog
import raftmessage
import raftrole


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

    ###   MULTI-PURPOSE HELPERS

    def count_majority(self) -> int:
        return 1 + len(self.config) // 2

    def create_followers_list(self) -> List[int]:
        followers = list(self.config.keys())
        followers.remove(self.identifier)

        return followers

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

        match state_change["match_index"]:
            case raftrole.Operation.RESET_TO_NONE:
                self.match_index = None
            case raftrole.Operation.INITIALIZE:
                self.match_index = {identifier: None for identifier in self.config}
                self.match_index[self.identifier] = len(self.log) - 1

        # Exception to RESET_TO_NONE, where reset is to -1. This is to simplify
        # message passing since integers are handled in the encoding/decoding
        # step, but None needs an extra step. Setting to -1 skip this step, but
        # care is needed at call sites to make sure change is via assignment
        # rather than addition.
        match state_change["commit_index"]:
            case raftrole.Operation.RESET_TO_NONE:
                self.commit_index = -1
            case raftrole.Operation.INITIALIZE:
                raise Exception("Invalid initialization operation for commit index.")

        match state_change["has_followers"]:
            case raftrole.Operation.RESET_TO_NONE:
                self.has_followers = None
            case raftrole.Operation.INITIALIZE:
                self.has_followers = False

        match state_change["voted_for"]:
            case raftrole.Operation.RESET_TO_NONE:
                self.voted_for = None
            case raftrole.Operation.INITIALIZE:
                self.voted_for = self.identifier

        match state_change["current_votes"]:
            case raftrole.Operation.RESET_TO_NONE:
                self.current_votes = None
            case raftrole.Operation.INITIALIZE:
                self.current_votes = {identifier: None for identifier in self.config}
                self.current_votes[self.identifier] = self.identifier

    ###   CLIENT-RELATED HANDLER

    def handle_client_log_append(
        self, source: int, target: int, item: str
    ) -> List[raftmessage.Message]:
        """
        Client adds a log entry (received by leader).
        """
        if self.role != raftrole.Role.LEADER:
            raise Exception("Not able to append entries when not leader.")

        self.log.append(raftlog.LogEntry(self.current_term, item))

        assert self.next_index is not None and self.match_index is not None
        self.next_index[target] = len(self.log)
        self.match_index[target] = len(self.log) - 1

        return []

    ###   LEADER-RELATED HELPERS AND HANDLERS

    def create_append_entries_arguments(
        self, target: int
    ) -> Tuple[int, int, int, List[raftlog.LogEntry], int]:
        assert self.next_index is not None
        next_index = self.next_index[target]

        assert next_index is not None
        previous_index = next_index - 1
        previous_term = (
            self.log[previous_index].term
            if len(self.log) > 0 and previous_index >= 0
            else -1
        )

        return (
            self.current_term,
            previous_index,
            previous_term,
            self.log[next_index:],
            self.commit_index,
        )

    def count_null_match_index(self) -> int:
        assert self.match_index is not None
        return len(
            [
                identifier
                for identifier in self.match_index.values()
                if identifier is None
            ]
        )

    def get_index_metrics(self) -> Tuple[int, int]:
        assert self.match_index is not None
        non_null_match_index_values = sorted(
            [value for value in self.match_index.values() if value is not None]
        )
        non_null_match_index_count = len(non_null_match_index_values)

        # Get median value with index corrected for null values
        median_match_index = self.count_majority() - 1 - self.count_null_match_index()

        if 0 <= median_match_index < len(non_null_match_index_values):
            potential_commit_index = non_null_match_index_values[median_match_index]

        else:
            potential_commit_index = -1

        return non_null_match_index_count, potential_commit_index

    def update_indexes(self, target: int, entries_length: int) -> None:
        assert self.next_index is not None and self.match_index is not None
        self.next_index[target] += entries_length
        self.match_index[target] = self.next_index[target] - 1

        # Change to leader's commit_index is only relevant after a successful
        # append entry response from follower.
        non_null_match_index_count, potential_commit_index = self.get_index_metrics()

        # Require at least majority of next_index to be non-null.
        if non_null_match_index_count < self.count_majority():
            return None

        # Require latest be entry from leader's current term.
        update_commit_index = (
            len(self.log) > 0
            and self.log[potential_commit_index].term == self.current_term
        )

        if update_commit_index or self.experimental_mode:
            self.commit_index = potential_commit_index

    def handle_leader_heartbeat(
        self,
        source: Optional[int] = None,
        target: Optional[int] = None,
        followers: Optional[List[int]] = None,
    ) -> List[raftmessage.Message]:
        """
        Leader heartbeat. Send AppendEntries to all followers.
        """
        if self.role != raftrole.Role.LEADER:
            raise Exception("Not able to generate leader heartbeat when not leader.")

        source = source or self.identifier
        target = target or self.identifier
        followers = followers or self.create_followers_list()

        messages: List[raftmessage.Message] = []

        for follower in followers:
            message = raftmessage.AppendEntryRequest(
                self.identifier,
                follower,
                *self.create_append_entries_arguments(follower),
            )
            messages.append(message)

        return messages

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
        """
        Update to the log (received by a follower).
        """
        state_change = raftrole.enumerate_state_change(
            raftrole.Role.LEADER, current_term, self.role, self.current_term
        )
        self.implement_state_change(state_change)

        # If not follower, then early return with no log changes.
        if self.role != raftrole.Role.FOLLOWER:
            return [
                raftmessage.AppendEntryResponse(
                    target,
                    source,
                    self.current_term,
                    False,
                    len(entries),
                )
            ]

        success = raftlog.append_entries(
            self.log, previous_index, previous_term, entries
        )

        # Movement of commit_index by follower is based on commit_index on
        # leader and length of own log.
        if commit_index > self.commit_index:
            self.commit_index = min(commit_index, len(self.log) - 1)

        return [
            raftmessage.AppendEntryResponse(
                target, source, self.current_term, success, len(entries)
            )
        ]

    def handle_append_entries_response(
        self,
        source: int,
        target: int,
        current_term: int,
        success: bool,
        entries_length: int,
    ) -> List[raftmessage.Message]:
        """
        Follower response (received by leader).
        """
        # Since leader target response is the same irrespective of source role,
        # simply use follower as source role.
        state_change = raftrole.enumerate_state_change(
            raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
        )
        self.implement_state_change(state_change)

        # If not leader, then early return with no log changes.
        if self.role != raftrole.Role.LEADER:
            return []

        # If successful, update indexes.
        if success:
            self.update_indexes(source, entries_length)

            assert self.has_followers is not None
            self.has_followers = True

            return []

        # If not successful, retry with earlier entries.
        assert self.next_index is not None and self.next_index[source] is not None
        self.next_index[source] = self.next_index[source] - 1

        return [
            raftmessage.AppendEntryRequest(
                target,
                source,
                *self.create_append_entries_arguments(source),
            )
        ]

    ###   CANDIDATE-RELATED HELPERS AND HANDLERS

    def count_self_votes(self) -> int:
        assert self.current_votes is not None
        return len(
            [
                identifier
                for identifier in self.current_votes.values()
                if identifier == self.identifier
            ]
        )

    def has_won_election(self) -> bool:
        return self.count_self_votes() >= self.count_majority()

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

        source = source or self.identifier
        target = target or self.identifier
        followers = followers or self.create_followers_list()

        messages: List[raftmessage.Message] = []

        previous_term = self.log[-1].term if len(self.log) > 0 else -1

        for follower in followers:
            message = raftmessage.RequestVoteRequest(
                self.identifier,
                follower,
                self.current_term,
                len(self.log) - 1,
                previous_term,
            )
            messages.append(message)

        return messages

    def handle_request_vote_request(
        self,
        source: int,
        target: int,
        current_term: int,
        last_log_index: int,
        last_log_term: int,
    ) -> List[raftmessage.Message]:
        state_change = raftrole.enumerate_state_change(
            raftrole.Role.CANDIDATE, current_term, self.role, self.current_term
        )
        self.implement_state_change(state_change)

        # If not follower, then early return with failed vote response.
        if self.role != raftrole.Role.FOLLOWER:
            return [
                raftmessage.RequestVoteResponse(
                    target, source, False, self.current_term
                )
            ]

        # Require candidate have higher term.
        if current_term < self.current_term:
            success = False

        # Require candidate have at least same log length.
        elif last_log_index < len(self.log) - 1:
            success = False

        # Require candidate have last entry having at least the same term.
        elif len(self.log) > 0 and last_log_term < self.log[-1].term:
            success = False

        else:
            assert current_term == self.current_term

            # Require vote not already cast to a different candidate.
            if self.voted_for is not None and self.voted_for != source:
                success = False

            else:
                if self.voted_for is None:
                    self.voted_for = source

                success = True

        return [
            raftmessage.RequestVoteResponse(target, source, success, self.current_term)
        ]

    def handle_request_vote_response(
        self,
        source: int,
        target: int,
        success: bool,
        current_term: int,
    ) -> List[raftmessage.Message]:
        # Since state change from candidate to follower on the back of a message
        # with equal term from a leader is only relevant for append entry
        # requests, can assume message from follower.
        state_change = raftrole.enumerate_state_change(
            raftrole.Role.FOLLOWER, current_term, self.role, self.current_term
        )
        self.implement_state_change(state_change)

        # If not candidate, then early return with no log changes.
        if self.role != raftrole.Role.CANDIDATE:
            return []

        if success:
            assert self.current_votes is not None
            self.current_votes[source] = target

            if self.has_won_election():
                state_change = raftrole.enumerate_state_change(
                    raftrole.Role.ELECTION_COMMISSION,
                    self.current_term,
                    self.role,
                    self.current_term,
                )
                self.implement_state_change(state_change)

                return [
                    raftmessage.UpdateFollowers(
                        self.identifier, self.identifier, self.create_followers_list()
                    )
                ]

        return []

    ###   ROLE CHANGE-RELATED HELPER AND HANDLER

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

        role_change = state_change["role_change"]
        assert role_change == (from_role, to_role)

        self.implement_state_change(state_change)
        return role_change

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
            case (raftrole.Role.LEADER, raftrole.Role.FOLLOWER):
                self.change_role(from_role, to_role)
                return []

            case _:
                raise Exception(
                    f"Role change from {from_role} to {to_role} on timeout not supported."
                )

    ###   CUSTOM HANDLERS

    def handle_text(
        self, source: int, target: int, text: str
    ) -> List[raftmessage.Message]:
        """
        Simplify testing by enabling state to be exposed.
        """
        if text.startswith("self"):
            text = "\n".join(
                [f"{item[0]}: {str(item[1])}" for item in sorted(vars(self).items())]
            )
            print("\n\n" + "\033[37m" + text)

        return []

    ###   PUBLIC INTERFACE

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

            case _:
                raise Exception(
                    "Exhaustive switch error on message type with message {message}."
                )


def change_state_on_timeout(state: RaftState) -> raftmessage.Message:
    """
    Carved out from class as state change on timeout is called from RaftServer
    rather than RaftState.
    """
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
            # Check that as leader, has_followers has been initialized.
            assert state.has_followers is not None

            # If no response received from previous heartbeat, step down as
            # leader.
            if not state.has_followers:
                return raftmessage.RoleChange(
                    state.identifier,
                    state.identifier,
                    raftrole.Role.LEADER,
                    raftrole.Role.FOLLOWER,
                )

            # Otherwise send out another heartbeat.
            state.has_followers = False

            return raftmessage.UpdateFollowers(
                state.identifier, state.identifier, state.create_followers_list()
            )

        case _:
            raise Exception("Exhaustive switch error on state change on timeout.")
