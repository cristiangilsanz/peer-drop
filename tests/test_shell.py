import pytest

from peer_drop.client import (
    Connect,
    GetFile,
    ListContent,
    ListUsers,
    Peer,
    Publish,
    Register,
)
from peer_drop.shell import Shell, main, port


class FakeClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    def register(self, user):
        self.calls.append(("register", user))
        return Register.TAKEN if user == "taken" else Register.OK

    def connect(self, user):
        self.calls.append(("connect", user))
        return Connect.OK

    def publish(self, path, description):
        self.calls.append(("publish", path, description))
        return Publish.OK

    def list_users(self):
        return ListUsers.OK, [Peer("alice", "10.0.0.1", 9001), Peer("bob", "10.0.0.2", 9002)]

    def list_content(self, owner):
        return ListContent.TARGET_UNKNOWN, []

    def get_file(self, owner, remote, local):
        self.calls.append(("get_file", owner, remote, local))
        return GetFile.MISSING

    def close(self):
        self.closed = True


@pytest.fixture
def shell():
    lines = []
    return Shell(FakeClient(), output=lines.append), lines


def test_commands_are_case_insensitive(shell):
    console, lines = shell
    console.execute("register alice")
    assert lines == ["REGISTER OK"]


def test_results_use_the_protocol_messages(shell):
    console, lines = shell
    console.execute("REGISTER taken")
    console.execute("LIST_CONTENT nobody")
    console.execute("GET_FILE bob song.mp3 copy.mp3")
    assert lines == [
        "USERNAME IN USE",
        "LIST_CONTENT FAIL, REMOTE USER DOES NOT EXIST",
        "GET_FILE FAIL, FILE NOT EXIST",
    ]


def test_listings_print_one_row_per_item(shell):
    console, lines = shell
    console.execute("LIST_USERS")
    assert lines == ["LIST_USERS OK", "\talice 10.0.0.1 9001", "\tbob 10.0.0.2 9002"]


def test_descriptions_keep_every_word(shell):
    console, _ = shell
    console.execute("PUBLISH notes.txt my lecture notes")
    console.execute('PUBLISH "my song.mp3" a song')
    assert console.client.calls == [
        ("publish", "notes.txt", "my lecture notes"),
        ("publish", "my song.mp3", "a song"),
    ]


def test_wrong_arguments_print_the_usage(shell):
    console, lines = shell
    console.execute("CONNECT")
    console.execute("LIST_USERS extra")
    console.execute(f"REGISTER {'x' * 300}")
    assert lines == [
        "Syntax error. Usage: CONNECT <userName>",
        "Syntax error. Usage: LIST_USERS",
        "Syntax error. Usage: REGISTER <userName>",
    ]


def test_unknown_commands_are_reported(shell):
    console, lines = shell
    console.execute("FLY away")
    console.execute("   ")
    assert lines == ["Error: Command 'FLY' not valid."]


def test_unreachable_servers_are_reported():
    class Offline(FakeClient):
        def register(self, user):
            raise ConnectionRefusedError

    lines = []
    Shell(Offline(), output=lines.append).execute("REGISTER alice")
    assert lines == ["REGISTER FAIL, CANNOT REACH THE SERVER"]


def test_help_lists_every_command(shell):
    console, lines = shell
    console.execute("HELP")
    assert len(lines) == len(console.commands)


def test_the_loop_stops_on_quit_and_closes_the_client(shell):
    console, lines = shell
    commands = iter(["REGISTER alice", "QUIT", "REGISTER never"])
    console.loop(read=lambda prompt: next(commands))
    assert lines == ["REGISTER OK", "+++ FINISHED +++"]
    assert console.client.closed


def test_the_loop_stops_at_end_of_input(shell):
    console, lines = shell

    def read(prompt):
        raise EOFError

    console.loop(read=read)
    assert lines == ["+++ FINISHED +++"]


def test_ports_must_be_unprivileged():
    assert port("4500") == 4500
    with pytest.raises(Exception, match="between 1024 and 65535"):
        port("80")


def test_the_server_address_is_required(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--server" in capsys.readouterr().err
