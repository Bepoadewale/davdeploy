"""Synthetic Step Functions task that can fail before recovery."""


def handler(event, _context):
    if event.get("should_fail"):
        raise RuntimeError("synthetic failure for Step Functions Catch test")
    return {
        "marker": event.get("marker"),
        "recovered": bool(event.get("failure_name")),
        "status": "ok",
    }
