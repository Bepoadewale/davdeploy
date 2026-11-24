def handler(event, _context):
    return {"version": "v1", "test_id": event.get("test_id")}
