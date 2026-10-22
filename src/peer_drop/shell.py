from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from peer_drop.client import (
    Connect,
    Delete,
    Disconnect,
    GetFile,
    ListContent,
    ListUsers,
    PeerDropClient,
    Publish,
    Register,
    Unregister,
)
from peer_drop.protocol import FIELD_LIMIT
from peer_drop.timestamp import DEFAULT_URL

PROMPT = "c> "
MESSAGES: dict[Enum, str] = {
    Register.OK: "REGISTER OK",
    Register.TAKEN: "USERNAME IN USE",
    Register.ERROR: "REGISTER FAIL",
    Unregister.OK: "UNREGISTER OK",
    Unregister.UNKNOWN: "USER DOES NOT EXIST",
    Unregister.ERROR: "UNREGISTER FAIL",
    Connect.OK: "CONNECT OK",
    Connect.UNKNOWN: "CONNECT FAIL, USER DOES NOT EXIST",
    Connect.ALREADY_CONNECTED: "USER ALREADY CONNECTED",
    Connect.ERROR: "CONNECT FAIL",
    Disconnect.OK: "DISCONNECT OK",
    Disconnect.UNKNOWN: "DISCONNECT FAIL, USER DOES NOT EXIST",
    Disconnect.NOT_CONNECTED: "DISCONNECT FAIL, USER NOT CONNECTED",
    Disconnect.ERROR: "DISCONNECT FAIL",
    Publish.OK: "PUBLISH OK",
    Publish.UNKNOWN: "PUBLISH FAIL, USER DOES NOT EXIST",
    Publish.NOT_CONNECTED: "PUBLISH FAIL, USER NOT CONNECTED",
    Publish.DUPLICATE: "PUBLISH FAIL, CONTENT ALREADY PUBLISHED",
    Publish.ERROR: "PUBLISH FAIL",
    Publish.MISSING_FILE: "PUBLISH FAIL, FILE NOT FOUND",
    Delete.OK: "DELETE OK",
    Delete.UNKNOWN: "DELETE FAIL, USER DOES NOT EXIST",
    Delete.NOT_CONNECTED: "DELETE FAIL, USER NOT CONNECTED",
    Delete.MISSING: "DELETE FAIL, CONTENT NOT PUBLISHED",
    Delete.ERROR: "DELETE FAIL",
    ListUsers.OK: "LIST_USERS OK",
    ListUsers.UNKNOWN: "LIST_USERS FAIL, USER DOES NOT EXIST",
    ListUsers.NOT_CONNECTED: "LIST_USERS FAIL, USER NOT CONNECTED",
    ListUsers.ERROR: "LIST_USERS FAIL",
    ListContent.OK: "LIST_CONTENT OK",
    ListContent.UNKNOWN: "LIST_CONTENT FAIL, USER DOES NOT EXIST",
    ListContent.NOT_CONNECTED: "LIST_CONTENT FAIL, USER NOT CONNECTED",
    ListContent.TARGET_UNKNOWN: "LIST_CONTENT FAIL, REMOTE USER DOES NOT EXIST",
    ListContent.ERROR: "LIST_CONTENT FAIL",
    GetFile.OK: "GET_FILE OK",
    GetFile.MISSING: "GET_FILE FAIL, FILE NOT EXIST",
    GetFile.ERROR: "GET_FILE FAIL",
}


@dataclass(frozen=True)
class Command:
    usage: str
    arity: int
    run: Callable[[list[str]], None]
    joins_rest: bool = False


class Shell:
    def __init__(self, client: PeerDropClient, output: Callable[[str], None] = print) -> None:
        self.client = client
        self.output = output
        self.running = True
        self.commands = {
            "REGISTER": Command("REGISTER <userName>", 1, self._register),
            "UNREGISTER": Command("UNREGISTER <userName>", 1, self._unregister),
            "CONNECT": Command("CONNECT <userName>", 1, self._connect),
            "DISCONNECT": Command("DISCONNECT <userName>", 1, self._disconnect),
            "PUBLISH": Command(
                "PUBLISH <fileName> <description>", 2, self._publish, joins_rest=True
            ),
            "DELETE": Command("DELETE <fileName>", 1, self._delete),
            "LIST_USERS": Command("LIST_USERS", 0, self._list_users),
            "LIST_CONTENT": Command("LIST_CONTENT <userName>", 1, self._list_content),
            "GET_FILE": Command(
                "GET_FILE <userName> <remoteFileName> <localFileName>", 3, self._get_file
            ),
            "HELP": Command("HELP", 0, self._help),
            "QUIT": Command("QUIT", 0, self._quit),
        }

    def execute(self, line: str) -> None:
        try:
            words = shlex.split(line)
        except ValueError:
            words = line.split()
        if not words:
            return
        name = words[0].upper()
        command = self.commands.get(name)
        if command is None:
            self.output(f"Error: Command '{words[0]}' not valid.")
            return
        args = words[1:]
        if command.joins_rest and len(args) > command.arity:
            args = [*args[: command.arity - 1], " ".join(args[command.arity - 1 :])]
        if len(args) != command.arity or any(len(arg) > FIELD_LIMIT for arg in args):
            self.output(f"Syntax error. Usage: {command.usage}")
            return
        try:
            command.run(args)
        except OSError:
            self.output(f"{name} FAIL, CANNOT REACH THE SERVER")

    def _say(self, result: Enum) -> None:
        self.output(MESSAGES[result])

    def _register(self, args: list[str]) -> None:
        self._say(self.client.register(args[0]))

    def _unregister(self, args: list[str]) -> None:
        self._say(self.client.unregister(args[0]))

    def _connect(self, args: list[str]) -> None:
        self._say(self.client.connect(args[0]))

    def _disconnect(self, args: list[str]) -> None:
        self._say(self.client.disconnect(args[0]))

    def _publish(self, args: list[str]) -> None:
        self._say(self.client.publish(args[0], args[1]))

    def _delete(self, args: list[str]) -> None:
        self._say(self.client.delete(args[0]))

    def _list_users(self, args: list[str]) -> None:
        result, peers = self.client.list_users()
        self._say(result)
        for peer in peers:
            self.output(f"\t{peer.name} {peer.address} {peer.port}")

    def _list_content(self, args: list[str]) -> None:
        result, files = self.client.list_content(args[0])
        self._say(result)
        for name in files:
            self.output(f"\t{name}")

    def _get_file(self, args: list[str]) -> None:
        self._say(self.client.get_file(*args))

    def _help(self, args: list[str]) -> None:
        for command in self.commands.values():
            self.output(f"\t{command.usage}")

    def _quit(self, args: list[str]) -> None:
        self.running = False

    def loop(self, read: Callable[[str], str] = input) -> None:
        while self.running:
            try:
                self.execute(read(PROMPT))
            except (EOFError, KeyboardInterrupt):
                break
        self.client.close()
        self.output("+++ FINISHED +++")


def port(value: str) -> int:
    number = int(value)
    if not 1024 <= number <= 65535:
        raise argparse.ArgumentTypeError("the port must be between 1024 and 65535")
    return number


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Share files with other PeerDrop users.")
    parser.add_argument("-s", "--server", required=True, help="address of the PeerDrop server")
    parser.add_argument(
        "-p", "--port", required=True, type=port, help="port of the PeerDrop server"
    )
    parser.add_argument(
        "--timestamp-url",
        default=os.environ.get("PEER_DROP_TIMESTAMP_URL", DEFAULT_URL),
        help="address of the timestamp service",
    )
    args = parser.parse_args(argv)
    client = PeerDropClient((args.server, args.port), timestamp_url=args.timestamp_url)
    Shell(client, output=lambda text: print(text, flush=True)).loop()
    sys.exit(0)
