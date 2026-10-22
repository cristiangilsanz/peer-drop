import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from werkzeug.serving import make_server

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
from peer_drop.timestamp import create_app

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "build" / "peer-drop-server"
LOGGER = ROOT / "build" / "peer-drop-logger"

pytestmark = pytest.mark.skipif(
    os.name == "nt" or not SERVER.exists(), reason="run make first to build the C server"
)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def rpcbind_running():
    rpcinfo = shutil.which("rpcinfo")
    if rpcinfo is None:
        return False
    return subprocess.run([rpcinfo, "-p", "127.0.0.1"], capture_output=True).returncode == 0


def wait_for(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def accepts(port):
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


class System:
    def __init__(self, directory):
        self.directory = directory
        self.port = free_port()
        self.server_log = directory / "server.log"
        self.logger_log = directory / "logger.log"
        self.logging = LOGGER.exists() and rpcbind_running()
        self.processes = []
        self.timestamps = make_server("127.0.0.1", 0, create_app())
        self.timestamp_url = f"http://127.0.0.1:{self.timestamps.server_port}/timestamp"

    def start(self):
        threading.Thread(target=self.timestamps.serve_forever, daemon=True).start()
        environment = dict(os.environ)
        if self.logging:
            self.logger = self._spawn([LOGGER], self.logger_log, environment)
            time.sleep(0.5)
            environment["PEER_DROP_LOGGER_HOST"] = "127.0.0.1"
        self.server = self._spawn([SERVER, "-p", str(self.port)], self.server_log, environment)
        assert wait_for(lambda: accepts(self.port)), "the server did not start"

    def _spawn(self, command, log, environment):
        process = subprocess.Popen(
            command, stdout=log.open("w"), stderr=subprocess.STDOUT, env=environment
        )
        self.processes.append(process)
        return process

    def client(self):
        return PeerDropClient(("127.0.0.1", self.port), timestamp_url=self.timestamp_url)

    def stop(self):
        self.server.send_signal(signal.SIGINT)
        self.exit_code = self.server.wait(timeout=10)
        for process in self.processes[:-1]:
            process.terminate()
            process.wait(timeout=10)
        self.timestamps.shutdown()


@pytest.fixture(scope="module")
def system(tmp_path_factory):
    instance = System(tmp_path_factory.mktemp("system"))
    instance.start()
    yield instance
    instance.stop()


@pytest.fixture
def peers(system):
    clients = [system.client(), system.client()]
    yield clients
    for client in clients:
        client.close()


def unique(name):
    return f"{name}-{time.monotonic_ns()}"


def test_two_peers_share_a_file(system, peers, tmp_path):
    alice, bob = peers
    alice_name, bob_name = unique("alice"), unique("bob")
    notes = tmp_path / "notes.txt"
    notes.write_text("meet at noon")

    assert alice.register(alice_name) is Register.OK
    assert bob.register(bob_name) is Register.OK
    assert alice.connect(alice_name) is Connect.OK
    assert bob.connect(bob_name) is Connect.OK
    assert bob.publish(str(notes), "meeting notes") is Publish.OK

    result, users = alice.list_users()
    assert result is ListUsers.OK
    assert {alice_name, bob_name} <= {user.name for user in users}
    assert alice.list_content(bob_name) == (ListContent.OK, ["notes.txt"])

    copy = tmp_path / "copy.txt"
    assert alice.get_file(bob_name, "notes.txt", str(copy)) is GetFile.OK
    assert copy.read_text() == "meet at noon"


def test_large_files_arrive_intact(system, peers, tmp_path):
    alice, bob = peers
    alice_name, bob_name = unique("alice"), unique("bob")
    payload = os.urandom(3 * 1024 * 1024)
    archive = tmp_path / "archive.bin"
    archive.write_bytes(payload)
    for client, name in ((alice, alice_name), (bob, bob_name)):
        client.register(name)
        client.connect(name)
    bob.publish(str(archive), "random bytes")
    copy = tmp_path / "received.bin"
    assert alice.get_file(bob_name, "archive.bin", str(copy)) is GetFile.OK
    assert copy.read_bytes() == payload


def test_peers_only_serve_published_files(system, peers, tmp_path):
    alice, bob = peers
    alice_name, bob_name = unique("alice"), unique("bob")
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    for client, name in ((alice, alice_name), (bob, bob_name)):
        client.register(name)
        client.connect(name)
    target = tmp_path / "stolen.txt"
    assert alice.get_file(bob_name, str(secret), str(target)) is GetFile.MISSING
    assert not target.exists()


def test_deleted_files_disappear_from_listings(system, peers, tmp_path):
    alice, bob = peers
    alice_name, bob_name = unique("alice"), unique("bob")
    song = tmp_path / "song.mp3"
    song.write_bytes(b"\x00\x01")
    for client, name in ((alice, alice_name), (bob, bob_name)):
        client.register(name)
        client.connect(name)
    assert bob.publish(str(song), "a song") is Publish.OK
    assert bob.publish(str(song), "again") is Publish.DUPLICATE
    assert bob.delete(str(song)) is Delete.OK
    assert bob.delete(str(song)) is Delete.MISSING
    assert alice.list_content(bob_name) == (ListContent.OK, [])
    assert alice.get_file(bob_name, "song.mp3", str(tmp_path / "x")) is GetFile.MISSING


def test_errors_follow_the_protocol(system, tmp_path):
    client = system.client()
    name = unique("carol")
    try:
        assert client.connect(name) is Connect.UNKNOWN
        assert client.register(name) is Register.OK
        assert client.register(name) is Register.TAKEN
        assert client.connect(name) is Connect.OK
        assert client.unregister(name) is Unregister.ERROR
        assert client.publish(str(tmp_path / "missing.txt"), "x") is Publish.MISSING_FILE
        assert client.list_content(unique("ghost"))[0] is ListContent.TARGET_UNKNOWN
        assert client.disconnect(name) is Disconnect.OK
        assert client.list_users() == (ListUsers.NOT_CONNECTED, [])
        assert client.unregister(name) is Unregister.OK
        assert client.unregister(name) is Unregister.UNKNOWN
    finally:
        client.close()


def test_names_cannot_escape_the_server(system):
    client = system.client()
    assert client.register("../../escape") is Register.OK
    assert client.unregister("../../escape") is Unregister.OK
    assert not (ROOT / "escape").exists()


def test_many_clients_register_at_once(system):
    names = [unique(f"user{index}") for index in range(40)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda name: system.client().register(name), names))
    assert results == [Register.OK] * len(names)


def test_the_server_reports_operations_as_they_happen(system):
    name = unique("dave")
    system.client().register(name)
    assert wait_for(lambda: f"OPERATION REGISTER FROM {name}" in system.server_log.read_text())


def test_the_logger_records_every_operation(system):
    if not system.logging:
        pytest.skip("rpcbind is not running")
    client = system.client()
    name = unique("erin")
    client.register(name)
    client.connect(name)
    client.close()
    assert wait_for(lambda: f"{name} DISCONNECT" in system.logger_log.read_text())
    lines = [line for line in system.logger_log.read_text().splitlines() if line.startswith(name)]
    assert [line.split()[1] for line in lines] == ["REGISTER", "CONNECT", "DISCONNECT"]


def test_unreachable_peers_fail_cleanly(system, peers, tmp_path):
    alice, bob = peers
    alice_name, bob_name = unique("alice"), unique("bob")
    for client, name in ((alice, alice_name), (bob, bob_name)):
        client.register(name)
        client.connect(name)
    bob.sharing.stop()
    target = tmp_path / "never.txt"
    assert alice.get_file(bob_name, "anything.txt", str(target)) is GetFile.ERROR
    assert not target.exists()
    assert not (tmp_path / ".never.txt.part").exists()
