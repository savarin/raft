"""
Combines state, network runtime and timer to act as a single Raft server.
"""

from typing import List
import dataclasses
import os
import random
import sys
import threading
import time

import raftmessage
import raftnode
import raftrole
import raftstate


TIMEOUT = 3


@dataclasses.dataclass
class RaftServer:
    identifier: int

    def __post_init__(self) -> None:
        self.state: raftstate.RaftState = raftstate.RaftState(self.identifier)
        self.node: raftnode.RaftNode = raftnode.RaftNode(self.identifier)
        self.timer: threading.Timer = threading.Timer(TIMEOUT, self.timeout)
        self.reset: bool = True

    def send(self, messages: List[raftmessage.Message]) -> None:
        for message in messages:
            self.node.send(message.target, raftmessage.encode_message(message))

    def cycle(self) -> None:
        timeout = TIMEOUT if self.state.role == raftrole.Role.LEADER else 2 * TIMEOUT

        self.timer.cancel()
        self.timer = threading.Timer(timeout, self.timeout)
        self.timer.start()

        self.reset = True

    def timeout(self) -> None:
        # Random timeout before starting elections.
        if self.state.role == raftrole.Role.FOLLOWER:
            time.sleep(random.random() * TIMEOUT)

        # Allow state change only when reset flag is set to True. This will
        # happen at the end of each cycle unless a leader heartbeat or follower
        # vote request/response is received.
        if self.reset:
            message = raftstate.change_state_on_timeout(self.state)
            self.node.incoming.put(raftmessage.encode_message(message))

        self.cycle()

    def color(self) -> str:
        return raftrole.color(self.state.role)

    def respond(self) -> None:
        while True:
            payload = self.node.receive()

            try:
                request = raftmessage.decode_message(payload)
                print(
                    self.color() + f"\n{request.source} > {request.target} {payload}",
                    end="",
                )

                # If receive leader heartbeat or vote request/response, set
                # reset flag to False to disable follower role change in the
                # current cycle.
                if (self.state.role, type(request)) in [
                    (raftrole.Role.FOLLOWER, raftmessage.AppendEntryRequest),
                    (raftrole.Role.FOLLOWER, raftmessage.RequestVoteRequest),
                    (raftrole.Role.CANDIDATE, raftmessage.RequestVoteResponse),
                ]:
                    self.reset = False

                if not isinstance(request, raftmessage.Text):
                    print(self.color() + f"\n{request.target} > ", end="")

                response = self.state.handle_message(request)
                self.send(response)

            except Exception as e:
                print(self.color() + f"Exception: {e}")

    def run(self):
        self.node.start()
        self.timer.start()
        self.respond()

        print(self.color() + "end.")
        os._exit(0)


if __name__ == "__main__":
    server = RaftServer(int(sys.argv[1]))
    server.run()
