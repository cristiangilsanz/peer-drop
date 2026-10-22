from __future__ import annotations

import socketserver
import threading
from pathlib import Path

from peer_drop.protocol import CHUNK_SIZE, Connection

GET_FILE = "GET FILE"


class FileCode:
    OK = 0
    MISSING = 1
    ERROR = 2


class _Handler(socketserver.BaseRequestHandler):
    server: _Server

    def handle(self) -> None:
        connection = Connection(self.request)
        try:
            command = connection.read_field()
            if command != GET_FILE:
                connection.send_bytes(bytes([FileCode.ERROR]))
                return
            path = self.server.owner.resolve(connection.read_field())
            if path is None:
                connection.send_bytes(bytes([FileCode.MISSING]))
                return
            connection.send_bytes(bytes([FileCode.OK]))
            connection.send(str(path.stat().st_size))
            with path.open("rb") as source:
                while chunk := source.read(CHUNK_SIZE):
                    connection.send_bytes(chunk)
        except (ConnectionError, OSError, UnicodeDecodeError):
            return


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, owner: PeerServer) -> None:
        self.owner = owner
        super().__init__(("", 0), _Handler)


class PeerServer:
    def __init__(self) -> None:
        self._shared: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._server: _Server | None = None

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("the peer server is not running")
        return self._server.server_address[1]

    @property
    def running(self) -> bool:
        return self._server is not None

    def start(self) -> None:
        if self._server is not None:
            return
        self._server = _Server(self)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None

    def share(self, name: str, path: Path) -> None:
        with self._lock:
            self._shared[name] = path

    def unshare(self, name: str) -> None:
        with self._lock:
            self._shared.pop(name, None)

    def resolve(self, name: str) -> Path | None:
        with self._lock:
            path = self._shared.get(name)
        return path if path is not None and path.is_file() else None
