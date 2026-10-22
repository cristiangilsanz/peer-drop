from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime

from flask import Flask, jsonify

TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5678
DEFAULT_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/timestamp"


def now() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/timestamp")
    def timestamp():
        return jsonify(timestamp=now())

    return app


def fetch_timestamp(url: str = DEFAULT_URL, timeout: float = 2.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return str(json.load(response)["timestamp"])
    except (OSError, ValueError, KeyError):
        return now()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve the current time to PeerDrop clients.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    create_app().run(host=args.host, port=args.port)
