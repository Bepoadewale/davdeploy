def handler(event, _context):
    return {"version": "v2", "test_id": event.get("test_id")}
