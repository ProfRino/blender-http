"""Blender HTTP client - sync or streaming script submission.

Usage:
    python send.py path\\to\\script.py
    python send.py path\\to\\script.py --stream
    python send.py path\\to\\script.py --url http://127.0.0.1:9877
"""

import argparse
import json
import sys
import urllib.request
from urllib.error import HTTPError


def main():
    ap = argparse.ArgumentParser(description="Send a Python script to Blender HTTP.")
    ap.add_argument("script", help="Path to a .py file")
    ap.add_argument("--url", default="http://127.0.0.1:9877")
    ap.add_argument("--stream", action="store_true", help="Use async + SSE streaming")
    args = ap.parse_args()

    with open(args.script, "rb") as f:
        body = f.read()

    if not args.stream:
        try:
            resp = urllib.request.urlopen(
                urllib.request.Request(args.url, data=body), timeout=600
            ).read().decode("utf-8")
        except HTTPError as e:
            resp = e.read().decode("utf-8")
        print(resp)
        return

    # Async + stream
    req = urllib.request.Request(f"{args.url}/jobs", data=body)
    job = json.loads(urllib.request.urlopen(req, timeout=30).read())
    jid = job["job_id"]
    print(f"job_id={jid}", file=sys.stderr)

    stream_url = f"{args.url}/jobs/{jid}/stream"
    with urllib.request.urlopen(stream_url, timeout=3600) as r:
        evt = ""
        for raw in r:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                evt = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
                print(f"[{evt}] {data}")
                if evt in ("completed", "failed", "cancelled"):
                    return


if __name__ == "__main__":
    main()
