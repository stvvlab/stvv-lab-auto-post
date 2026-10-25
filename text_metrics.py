"""Shared conservative X length accounting (URLs count as 23)."""
import re


def x_length(message):
    count = 0
    previous = 0

    for match in re.finditer(r"https?://\S+", message):
        count += sum(
            1 if ord(c) < 128 else 2
            for c in message[previous:match.start()]
        ) + 23
        previous = match.end()

    return count + sum(
        1 if ord(c) < 128 else 2
        for c in message[previous:]
    )
