"""A tiny module, well under the 200-LoC outline threshold.

Files this small are returned by passthrough (empty outline) because
reading them whole is cheap; the outline tax is not worth paying.
"""


def greet(name: str) -> str:
    """Return a friendly greeting."""
    return f"hello, {name}"


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


class Counter:
    """A trivial incrementing counter."""

    def __init__(self) -> None:
        self.value = 0

    def increment(self) -> int:
        self.value += 1
        return self.value
