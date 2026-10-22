from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from peer_drop.peer import GET_FILE, FileCode, PeerServer
from peer_drop.protocol import connect
from peer_drop.timestamp import DEFAULT_URL, fetch_timestamp


class Register(Enum):
    OK = 0
    TAKEN = 1
    ERROR = 2


class Unregister(Enum):
    OK = 0
    UNKNOWN = 1
    ERROR = 2


class Connect(Enum):
    OK = 0
    UNKNOWN = 1
    ALREADY_CONNECTED = 2
    ERROR = 3


class Disconnect(Enum):
    OK = 0
    UNKNOWN = 1
    NOT_CONNECTED = 2
    ERROR = 3


class Publish(Enum):
    OK = 0
    UNKNOWN = 1
    NOT_CONNECTED = 2
    DUPLICATE = 3
    ERROR = 4
    MISSING_FILE = 5


class Delete(Enum):
    OK = 0
    UNKNOWN = 1
    NOT_CONNECTED = 2
    MISSING = 3
    ERROR = 4


class ListUsers(Enum):
    OK = 0
    UNKNOWN = 1
    NOT_CONNECTED = 2
    ERROR = 3


class ListContent(Enum):
    OK = 0
    UNKNOWN = 1
    NOT_CONNECTED = 2
    TARGET_UNKNOWN = 3
    ERROR = 4


class GetFile(Enum):
    OK = 0
    MISSING = 1
    ERROR = 2


@dataclass(frozen=True)
class Peer:
    name: str
    address: str
    port: int


def shared_name(path: str) -> str:
    return Path(path).name


class PeerDropClient:
    def __init__(
        self,
        server: tuple[str, int],
        timestamp_url: str = DEFAULT_URL,
        timeout: float = 5.0,
        clock: Callable[[str], str] = fetch_timestamp,
    ) -> None:
        self.server = server
        self.timestamp_url = timestamp_url
        self.timeout = timeout
        self.clock = clock
        self.user: str | None = None
        self.sharing = PeerServer()

    def _call(self, command: str, *fields: str) -> int:
        with connect(self.server, self.timeout) as connection:
            connection.send(command, self.clock(self.timestamp_url), *fields)
            return connection.read_code()

    def register(self, user: str) -> Register:
        return Register(self._call("REGISTER", user))

    def unregister(self, user: str) -> Unregister:
        return Unregister(self._call("UNREGISTER", user))

    def connect(self, user: str) -> Connect:
        if self.user is not None:
            self.disconnect(self.user)
        self.sharing.start()
        result = Connect(self._call("CONNECT", user, str(self.sharing.port)))
        if result is Connect.OK:
            self.user = user
        else:
            self.sharing.stop()
        return result

    def disconnect(self, user: str) -> Disconnect:
        if self.user is None:
            return Disconnect.NOT_CONNECTED
        if user != self.user:
            return Disconnect.ERROR
        result = Disconnect(self._call("DISCONNECT", user))
        if result in (Disconnect.OK, Disconnect.UNKNOWN, Disconnect.NOT_CONNECTED):
            self.user = None
            self.sharing.stop()
        return result

    def publish(self, path: str, description: str) -> Publish:
        if self.user is None:
            return Publish.NOT_CONNECTED
        local = Path(path).expanduser()
        if not local.is_file():
            return Publish.MISSING_FILE
        name = shared_name(path)
        result = Publish(self._call("PUBLISH", self.user, name, description))
        if result is Publish.OK:
            self.sharing.share(name, local.resolve())
        return result

    def delete(self, path: str) -> Delete:
        if self.user is None:
            return Delete.NOT_CONNECTED
        name = shared_name(path)
        result = Delete(self._call("DELETE", self.user, name))
        if result is Delete.OK:
            self.sharing.unshare(name)
        return result

    def list_users(self) -> tuple[ListUsers, list[Peer]]:
        if self.user is None:
            return ListUsers.NOT_CONNECTED, []
        with connect(self.server, self.timeout) as connection:
            connection.send("LIST_USERS", self.clock(self.timestamp_url), self.user)
            result = ListUsers(connection.read_code())
            if result is not ListUsers.OK:
                return result, []
            count = connection.read_number()
            peers = [
                Peer(connection.read_field(), connection.read_field(), connection.read_number())
                for _ in range(count)
            ]
            return result, peers

    def list_content(self, owner: str) -> tuple[ListContent, list[str]]:
        if self.user is None:
            return ListContent.NOT_CONNECTED, []
        with connect(self.server, self.timeout) as connection:
            connection.send("LIST_CONTENT", self.clock(self.timestamp_url), self.user, owner)
            result = ListContent(connection.read_code())
            if result is not ListContent.OK:
                return result, []
            count = connection.read_number()
            return result, [connection.read_field() for _ in range(count)]

    def get_file(self, owner: str, remote: str, local: str) -> GetFile:
        if self.user is None or owner == self.user:
            return GetFile.ERROR
        result, peers = self.list_users()
        peer = next((item for item in peers if item.name == owner), None)
        if result is not ListUsers.OK or peer is None:
            return GetFile.ERROR
        target = Path(local).expanduser()
        partial = target.with_name(f".{target.name}.part")
        try:
            result = self._download(peer, shared_name(remote), partial)
        except (OSError, ValueError):
            result = GetFile.ERROR
        if result is GetFile.OK:
            os.replace(partial, target)
        else:
            partial.unlink(missing_ok=True)
        return result

    def _download(self, peer: Peer, name: str, partial: Path) -> GetFile:
        with connect((peer.address, peer.port), self.timeout) as connection:
            connection.send(GET_FILE, name)
            code = connection.read_code()
            if code == FileCode.MISSING:
                return GetFile.MISSING
            if code != FileCode.OK:
                return GetFile.ERROR
            size = connection.read_number()
            with partial.open("wb") as sink:
                for chunk in connection.read_chunks(size):
                    sink.write(chunk)
        return GetFile.OK

    def close(self) -> None:
        if self.user is not None:
            with contextlib.suppress(OSError):
                self.disconnect(self.user)
        self.sharing.stop()
