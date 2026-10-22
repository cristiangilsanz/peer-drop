import re

from peer_drop.timestamp import create_app, fetch_timestamp

PATTERN = re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}")


def test_the_service_returns_the_current_time():
    response = create_app().test_client().get("/timestamp")
    assert response.status_code == 200
    assert PATTERN.fullmatch(response.get_json()["timestamp"])


def test_clients_fall_back_to_the_local_clock():
    assert PATTERN.fullmatch(fetch_timestamp("http://127.0.0.1:9/timestamp", timeout=0.2))
