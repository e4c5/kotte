"""Tests for structured logging."""

import json
import logging

from app.core.logging import JSONFormatter


def test_json_formatter_includes_request_id_when_absent():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    line = formatter.format(record)
    data = json.loads(line)
    assert "request_id" in data
    assert data["request_id"] is None


def test_json_formatter_includes_request_id_from_extra():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc-123"
    line = formatter.format(record)
    data = json.loads(line)
    assert data["request_id"] == "abc-123"
