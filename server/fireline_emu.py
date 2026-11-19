"""Local Fireline emulator for Fractured Space (offline play).

Based on Tigerhacker/refireline (GPL-3.0): serves pre-recorded responses
from the original api.fireteam.net. Unknown requests are logged so the
missing endpoints can be added.

Usage:
  python fireline_emu.py                 -> http on 127.0.0.1:8080
  python fireline_emu.py --https CERT KEY -> https on 127.0.0.1:443
"""
import json
import os
import sys
import datetime
from flask import Flask, request, Response

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "responses.json")
LOG = os.path.join(HERE, "requests.log")
PREFIX = "https://api.fireteam.net/"

app = Flask(__name__)
canned = {}  # (method, path) -> entry

with open(DATA, encoding="utf-8") as fh:
    for entry in json.load(fh):
        url = entry["request"]["url"]
        path = url[len(PREFIX):].split("?", 1)[0] if url.startswith(PREFIX) else url
        canned[(entry["request"]["method"], path)] = entry


def log(line):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")
    print(line, flush=True)


@app.route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def root():
    log(f"{request.method} / ")
    return "Fireline Emulator for Fractured Space (local)"


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def any_path(path):
    entry = canned.get((request.method, path))
    if entry is None:
        # Fall back: same path with any method (e.g. PUT player_data -> GET copy)
        entry = next((e for (m, p), e in canned.items() if p == path), None)
    if entry is None:
        body = request.get_data(as_text=True)[:300]
        log(f"MISS {request.method} /{path}?{request.query_string.decode()} body={body!r}")
        return Response(json.dumps({}), status=200, mimetype="application/json")
    log(f"hit  {request.method} /{path}")
    return Response(entry["response"]["content"],
                    status=entry["response"]["status_code"],
                    mimetype="application/json")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--https":
        app.run(host="127.0.0.1", port=443, threaded=True,
                ssl_context=(sys.argv[2], sys.argv[3]))
    else:
        app.run(host="127.0.0.1", port=8080, threaded=True)
