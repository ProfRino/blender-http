"""Server-Sent Events emission for job progress."""

import json
import time


def emit(job, event_type: str, data: dict):
    evt = {"type": event_type, "ts": time.time(), "data": data}
    with job.event_cond:
        job.events.append(evt)
        job.event_cond.notify_all()


def format_sse(evt: dict) -> str:
    return f"event: {evt['type']}\ndata: {json.dumps(evt['data'])}\n\n"
