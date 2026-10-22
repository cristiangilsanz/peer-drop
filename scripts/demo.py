from __future__ import annotations

import argparse
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from subprocess import PIPE, Popen

PROMPT = b"c> "
PHOTO = bytes(range(256)) * 64

SCENARIO = [
    ("bob", "REGISTER bob"),
    ("bob", "CONNECT bob"),
    ("bob", "PUBLISH holiday.jpg Photos from the beach"),
    ("alice", "REGISTER alice"),
    ("alice", "CONNECT alice"),
    ("alice", "LIST_USERS"),
    ("alice", "LIST_CONTENT bob"),
    ("alice", "GET_FILE bob holiday.jpg holiday.jpg"),
    ("alice", "DISCONNECT alice"),
    ("bob", "DISCONNECT bob"),
    ("alice", "UNREGISTER alice"),
    ("bob", "UNREGISTER bob"),
]

Listener = Callable[[str, str], None]


class Terminal:
    def __init__(self, name: str, folder: Path, command: list[str]) -> None:
        self.name = name
        self.folder = folder
        self.process = Popen(command, cwd=folder, stdin=PIPE, stdout=PIPE)

    def read_until_prompt(self) -> str:
        assert self.process.stdout is not None
        output = bytearray()
        while not output.endswith(PROMPT):
            byte = self.process.stdout.read(1)
            if not byte:
                break
            output.extend(byte)
        return output[: -len(PROMPT)].decode() if output.endswith(PROMPT) else output.decode()

    def run(self, command: str) -> str:
        assert self.process.stdin is not None
        self.process.stdin.write(f"{command}\n".encode())
        self.process.stdin.flush()
        return self.read_until_prompt()

    def quit(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(b"QUIT\n")
        self.process.stdin.close()
        self.process.wait(timeout=10)


def run(server: str, port: int, timestamp_url: str, listen: Listener, pace: float = 0.0) -> bool:
    with tempfile.TemporaryDirectory() as root:
        folders = {name: Path(root) / name for name in ("alice", "bob")}
        for folder in folders.values():
            folder.mkdir()
        (folders["bob"] / "holiday.jpg").write_bytes(PHOTO)
        command = [sys.executable, "-m", "peer_drop", "-s", server, "-p", str(port)]
        terminals = {
            name: Terminal(name, folder, [*command, "--timestamp-url", timestamp_url])
            for name, folder in folders.items()
        }
        for terminal in terminals.values():
            terminal.read_until_prompt()
        for name, line in SCENARIO:
            listen(name, f"c> {line}")
            for output in terminals[name].run(line).splitlines():
                listen(name, output)
            time.sleep(pace)
        for terminal in terminals.values():
            terminal.quit()
        received = folders["alice"] / "holiday.jpg"
        return received.exists() and received.read_bytes() == PHOTO


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a scripted PeerDrop session between two peers."
    )
    parser.add_argument("--server", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4500)
    parser.add_argument("--timestamp-url", default="http://localhost:5678/timestamp")
    args = parser.parse_args()
    ok = run(
        args.server, args.port, args.timestamp_url, lambda name, text: print(f"{name:>5} | {text}")
    )
    print("alice received bob's photo intact" if ok else "the photo did not arrive intact")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
