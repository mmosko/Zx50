from typing import Protocol


class Readable(Protocol):

    def read(self) -> bytes:
        ...
