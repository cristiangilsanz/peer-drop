import pytest

from peer_drop.peer import GET_FILE, FileCode, PeerServer
from peer_drop.protocol import connect


@pytest.fixture
def peer():
    server = PeerServer()
    server.start()
    yield server
    server.stop()


def request(server, *fields):
    with connect(("127.0.0.1", server.port), timeout=5) as connection:
        connection.send(*fields)
        code = connection.read_code()
        if code != FileCode.OK:
            return code, None
        size = connection.read_number()
        return code, connection.read_exact(size)


def test_serves_published_files(peer, tmp_path):
    song = tmp_path / "song.txt"
    song.write_bytes(b"la la la")
    peer.share("song.txt", song)
    assert request(peer, GET_FILE, "song.txt") == (FileCode.OK, b"la la la")


def test_never_serves_files_that_were_not_published(peer, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    assert request(peer, GET_FILE, str(secret)) == (FileCode.MISSING, None)
    assert request(peer, GET_FILE, "secret.txt") == (FileCode.MISSING, None)


def test_unshared_files_stop_being_served(peer, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("hi")
    peer.share("notes.txt", notes)
    peer.unshare("notes.txt")
    assert request(peer, GET_FILE, "notes.txt") == (FileCode.MISSING, None)


def test_deleted_local_files_are_reported_missing(peer, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("hi")
    peer.share("notes.txt", notes)
    notes.unlink()
    assert request(peer, GET_FILE, "notes.txt") == (FileCode.MISSING, None)


def test_unknown_commands_are_errors(peer):
    assert request(peer, "PUT FILE", "x") == (FileCode.ERROR, None)


def test_the_port_requires_a_running_server():
    server = PeerServer()
    with pytest.raises(RuntimeError):
        _ = server.port
