"""BE-91 assertions shared by the refusal regression suites."""

import json
from uuid import UUID


def assert_error(raw, code, message_key):
    body = json.loads(raw)
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message_key", "error_id"}
    assert error["code"] == code
    assert error["message_key"] == message_key
    assert str(UUID(error["error_id"], version=4)) == error["error_id"]
