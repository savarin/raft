# Chapter 4: Message Encoding with Bencode

## Introduction

This chapter covers how messages are serialized for network transmission. The implementation uses Bencode, a simple encoding format from BitTorrent. While not essential to understanding Raft's algorithm, the encoding layer shows how abstract message types become bytes on the wire. The `rafthelpers.py` module handles this translation.

## 4.1 Why Bencode?

Bencode offers several properties that make it suitable for a learning implementation:

**Simplicity**: Only four data types (integers, strings, lists, dictionaries). No schemas, no version numbers, no configuration.

**Unambiguous**: Each value has exactly one encoding. Unlike JSON, there's no whitespace flexibility or key ordering variation.

**Self-delimiting**: You can tell where one value ends and the next begins without external framing (though this implementation adds length-prefixing at the socket layer).

**Human-readable** (mostly): While not as clean as JSON, you can often read Bencode by eye. `i42e` is clearly 42. `3:foo` is clearly "foo".

For a production system, you might choose Protocol Buffers or MessagePack for efficiency. But Bencode's simplicity makes it easy to debug and understand.

## 4.2 The Bencode Format

Bencode defines four data types:

**Integers**: Encoded as `i<number>e`
```
42      → i42e
-17     → i-17e
0       → i0e
```

**Strings**: Encoded as `<length>:<content>`
```
"foo"   → 3:foo
""      → 0:
"hello" → 5:hello
```

**Lists**: Encoded as `l<elements>e`
```
[1, "foo"]          → li1e3:fooe
[[1, 2], [3, 4]]    → lli1ei2eeli3ei4eee
```

**Dictionaries**: Encoded as `d<key><value>...e` with keys sorted
```
{"foo": 1}              → d3:fooi1ee
{"a": 1, "b": 2}        → d1:ai1e1:bi2ee
```

Note that dictionary keys must be strings, and they're sorted lexicographically in the encoded output. This ensures the same dictionary always encodes identically.

## 4.3 Encoding Implementation

The `encode_item` function in `rafthelpers.py` uses pattern matching on Python types:

```python
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
            raise Exception(f"Exhaustive switch error in encoding item {element}.")
```

Key observations:

- `None` encodes as empty string (a pragmatic choice for this implementation)
- Lists recursively encode each element
- Dictionaries sort their items before encoding (ensuring deterministic output)
- Unknown types raise an exception rather than silently failing

## 4.4 Decoding Implementation

Decoding is more complex because you need to consume the input string incrementally. The implementation uses a closure that returns both the decoded value and the remaining unparsed string:

```python
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

            rest = rest[1:]  # consume the 'e'

            if string.startswith("l"):
                return elements, rest

            return {k: v for k, v in zip(elements[::2], elements[1::2])}, rest

        else:
            raise Exception(f"Malformed string {string}.")

    return closure(string)[0]
```

The closure pattern enables recursive descent parsing:

1. Check the first character to determine the type
2. Parse that type (possibly recursing for nested structures)
3. Return the value and remaining string
4. The caller continues parsing from where we left off

For lists and dicts, we loop until we see `e`, collecting elements. For dicts, we pair up alternating elements as keys and values.

## 4.5 Round-Trip Testing

The test suite verifies that encoding followed by decoding returns the original value:

```python
def test_encode_items():
    assert rafthelpers.encode_item(None) == ""
    assert rafthelpers.encode_item("") == "0:"
    assert rafthelpers.encode_item([]) == "le"
    assert rafthelpers.encode_item({}) == "de"

    assert rafthelpers.encode_item(1) == "i1e"
    assert rafthelpers.encode_item(-1) == "i-1e"
    assert rafthelpers.encode_item("foo") == "3:foo"

    assert rafthelpers.encode_item([1, "foo"]) == "li1e3:fooe"
    assert rafthelpers.encode_item({"foo": 1}) == "d3:fooi1ee"

    # Nested structures
    assert rafthelpers.encode_item([1, ["foo"]]) == "li1el3:fooee"
    assert rafthelpers.encode_item({"foo": {"bar": "baz"}}) == "d3:food3:bar3:bazee"


def test_decode_items():
    assert rafthelpers.decode_item("") == None
    assert rafthelpers.decode_item("0:") == ""
    assert rafthelpers.decode_item("le") == []
    assert rafthelpers.decode_item("de") == {}

    assert rafthelpers.decode_item("i1e") == 1
    assert rafthelpers.decode_item("i-1e") == -1
    assert rafthelpers.decode_item("3:foo") == "foo"

    assert rafthelpers.decode_item("li1e3:fooe") == [1, "foo"]
    assert rafthelpers.decode_item("d3:fooi1ee") == {"foo": 1}
```

These tests cover edge cases: empty values, negative numbers, nested structures. The symmetry between encode and decode tests makes it easy to verify correctness.

## 4.6 Message Serialization

The `raftmessage.py` module builds on Bencode to serialize typed messages:

```python
def encode_message(message: Message) -> str:
    attributes = vars(message).copy()

    match message:
        case AppendEntryRequest():
            entries = []
            for entry in message.entries:
                entries.append(vars(entry))
            attributes["message_type"] = MessageType.APPEND_REQUEST.value
            attributes["entries"] = entries

        case AppendEntryResponse():
            attributes["message_type"] = MessageType.APPEND_RESPONSE.value
            attributes["success"] = int(attributes["success"])

        # ... other cases

    return rafthelpers.encode_item(attributes)
```

Each message type needs special handling:
- A `message_type` field is added for dispatch on the receiving end
- Nested objects (like `LogEntry` lists) are converted to dicts
- Booleans are converted to integers (Bencode doesn't have booleans)
- Enum values are converted to strings

The decoder reverses these transformations:

```python
def decode_message(string: str) -> Message:
    attributes = rafthelpers.decode_item(string)
    message_type = MessageType(attributes["message_type"])
    del attributes["message_type"]

    match message_type:
        case MessageType.APPEND_REQUEST:
            entries = []
            for entry in attributes["entries"]:
                entries.append(raftlog.LogEntry(**entry))
            attributes["entries"] = entries
            return AppendEntryRequest(**attributes)

        case MessageType.APPEND_RESPONSE:
            attributes["success"] = bool(attributes["success"])
            return AppendEntryResponse(**attributes)

        # ... other cases
```

## Conclusion

Bencode provides a simple serialization format for Raft messages. The `encode_item` and `decode_item` functions in `rafthelpers.py` handle the translation between Python objects and wire format using recursive pattern matching. The message layer adds type information and handles special cases like nested objects and enums. This encoding layer sits beneath the message types, invisible to the protocol logic above.
