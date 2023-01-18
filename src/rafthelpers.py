import builtins
import re


class DecodeError(Exception):
    pass


def encode_item(element):
    if element is None:
        return ""

    match type(element):
        case builtins.int:
            return f"i{str(element)}e"

        case builtins.str:
            return f"{len(element)}:{element}"

        case builtins.list:
            return "l" + "".join([encode_item(item) for item in element]) + "e"

        case builtins.dict:
            collection = []

            for pair in sorted(element.items()):
                for item in pair:
                    collection.append(item)

            return "d" + "".join([encode_item(item) for item in collection]) + "e"

        case _:
            raise Exception("Exhaustive switch error.")


def decode_item(string):
    def closure(string):
        if string == "":
            return None, ""

        elif string.startswith("i"):
            match = re.match("i(-?\\d+)e", string)
            return int(match.group(1)), string[match.span()[1] :]

        elif string[0] in "0123456789":
            match = re.match("(\\d+):", string)
            start = match.span()[1]
            end = start + int(match.group(1))
            return string[start:end], string[end:]

        elif string[0] in {"l", "d"}:
            elements = []
            rest = string[1:]

            while not rest.startswith("e"):
                element, rest = closure(rest)
                elements.append(element)

            rest = rest[1:]

            if string.startswith("l"):
                return elements, rest

            return {k: v for k, v in zip(elements[::2], elements[1::2])}, rest

        else:
            raise DecodeError("Malformed string.")

    return closure(string)[0]


if __name__ == "__main__":
    breakpoint()
