from typing import List
import dataclasses


@dataclasses.dataclass
class LogEntry:
    term: int
    item: str


def append_entry(
    log: List[LogEntry], previous_index: int, previous_term: int, entry: LogEntry
):
    """
    Choose index starting from 0.

    Suppose have 3 elements. Either append starting at previous_index 2 or
    modify at 0 or 1, returning True. Returns False if try to previous_index
    3 or more.

    [a b c]  d e 4
     ^ ^ ^   ^ ^ ^
     0 1 2   3 4 5
    """
    if 0 <= previous_index < len(log):
        if previous_index < len(log) - 1:
            log[previous_index + 1] = entry
            return True

        elif previous_index == len(log) - 1:
            log.append(entry)
            return True

    return False


def append_entries(
    log: List[LogEntry],
    previous_index: int,
    previous_term: int,
    entries: List[LogEntry],
):
    # Check index rewrite does not create gaps. If it does, return False.
    if previous_index >= len(log):
        return False

    elif 0 <= previous_index < len(log):
        # Check term number of previous entry matches previous_term.
        if log[previous_index].term != previous_term:
            return False

        # If term number of existing entry is less than term of entry to be
        # replaced, remove that entry and following entries.
        if previous_index + 1 <= len(log) - 1 and len(entries) > 0:
            if log[previous_index].term < entries[0].term:
                for _ in range(len(log) - previous_index - 2):
                    log.pop()

    # Require appends to the start of the log is to an empty log.
    if previous_index == -1:
        if len(log) == 0:
            log += entries
            return True

        return False

    for i, entry in enumerate(entries):
        if not append_entry(log, previous_index + i, previous_term, entry):
            return False

    return True
