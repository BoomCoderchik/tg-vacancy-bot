from __future__ import annotations

import sys


def write_stdout(text: str) -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") == "utf8":
        print(text)
        return
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
