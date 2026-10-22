import socket
import threading

import pytest

from peer_drop.protocol import FIELD_LIMIT, Connection, encode


@pytest.fixture
def pair():
    left, right = socket.socketpair()
    yield Connection(left), right
    left.close()
    right.close()


def test_fields_are_null_terminated():
    assert encode("REGISTER", "alice") == b"REGISTER\0alice\0"


def test_fields_are_utf8():
    assert encode("caf\u00e9") == "caf\u00e9".encode() + b"\0"


def test_reads_fields_split_across_packets(pair):
    connection, peer = pair

    def send_slowly():
        for byte in b"LIST\0al":
            peer.send(bytes([byte]))
        peer.send(b"ice\0" + b"42\0")

    thread = threading.Thread(target=send_slowly)
    thread.start()
    assert connection.read_field() == "LIST"
    assert connection.read_field() == "alice"
    assert connection.read_number() == 42
    thread.join()


def test_reads_codes_and_exact_bytes(pair):
    connection, peer = pair
    peer.sendall(bytes([3]) + b"payload")
    assert connection.read_code() == 3
    assert connection.read_exact(7) == b"payload"


def test_streams_chunks_of_the_requested_size(pair):
    connection, peer = pair
    peer.sendall(b"0\0" + b"x" * 5000 + b"tail")
    assert connection.read_field() == "0"
    assert b"".join(connection.read_chunks(5000)) == b"x" * 5000
    assert connection.read_exact(4) == b"tail"


def test_closed_connections_raise(pair):
    connection, peer = pair
    peer.sendall(b"partial")
    peer.close()
    with pytest.raises(ConnectionError):
        connection.read_field()


def test_oversized_fields_are_rejected(pair):
    connection, peer = pair
    peer.sendall(b"a" * (FIELD_LIMIT + 10))
    with pytest.raises(ConnectionError):
        connection.read_field()
