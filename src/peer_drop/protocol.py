from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager

FIELD_LIMIT = 255
ENCODING = "utf-8"
CHUNK_SIZE = 64 * 1024


def encode(*fields: str) -> bytes:
    return b"".join(field.encode(ENCODING) + b"\0" for field in fields)


class Connection:
    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock
        self._buffer = bytearray()

    def send(self, *fields: str) -> None:
        self._socket.sendall(encode(*fields))

    def send_bytes(self, data: bytes) -> None:
        self._socket.sendall(data)

    def _fill(self) -> None:
        chunk = self._socket.recv(CHUNK_SIZE)
        if not chunk:
            raise ConnectionError("the connection closed before the reply was complete")
        self._buffer.extend(chunk)

    def read_exact(self, size: int) -> bytes:
        while len(self._buffer) < size:
            self._fill()
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def read_chunks(self, size: int) -> Iterator[bytes]:
        remaining = size
        while remaining > 0:
            if not self._buffer:
                self._fill()
            chunk = bytes(self._buffer[:remaining])
            del self._buffer[: len(chunk)]
            remaining -= len(chunk)
            yield chunk

    def read_code(self) -> int:
        return self.read_exact(1)[0]

    def read_field(self) -> str:
        while b"\0" not in self._buffer:
            if len(self._buffer) > FIELD_LIMIT:
                raise ConnectionError("a field was longer than the protocol allows")
            self._fill()
        end = self._buffer.index(b"\0")
        field = bytes(self._buffer[:end]).decode(ENCODING)
        del self._buffer[: end + 1]
        return field

    def read_number(self) -> int:
        return int(self.read_field())


@contextmanager
def connect(address: tuple[str, int], timeout: float) -> Iterator[Connection]:
    with socket.create_connection(address, timeout=timeout) as sock:
        yield Connection(sock)
