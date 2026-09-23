"""Exercise raw ASGI streaming independently of multipart parsing."""
import asyncio
import json

import pytest

from app.api import upload_limit


def exercise(monkeypatch, chunks, *, headers=None, path="/api/v1/datasets/import"):
    monkeypatch.setattr(upload_limit, "MAX_IMPORT_BYTES", 8)
    messages = [{"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
                for index, chunk in enumerate(chunks)]
    sent, received_by_app, calls = [], [], []
    reads = 0

    async def receive():
        nonlocal reads
        reads += 1
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def app(scope, incoming, outgoing):
        calls.append(scope)
        while True:
            message = await incoming()
            received_by_app.append(message)
            if not message.get("more_body", False):
                break
        # A second receive must not replay the buffered body again.
        received_by_app.append(await incoming())
        await outgoing({"type": "http.response.start", "status": 204, "headers": []})
        await outgoing({"type": "http.response.body", "body": b""})

    scope = {"type": "http", "method": "POST", "path": path, "headers": headers or []}
    asyncio.run(upload_limit.ImportBodyLimit(app)(scope, receive, send))
    return sent, received_by_app, calls, reads


def test_declared_overlimit_rejected_before_reading(monkeypatch):
    sent, incoming, calls, reads = exercise(monkeypatch, [b"small"],
                                           headers=[(b"content-length", b"9")])
    assert sent[0]["status"] == 413
    assert (b"cache-control", b"no-store") in sent[0]["headers"]
    assert "exceeds" in json.loads(sent[1]["body"])["detail"]
    assert incoming == calls == []
    assert reads == 0


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"2")]])
def test_streamed_limit_enforced_without_trusting_header(monkeypatch, headers):
    sent, incoming, calls, reads = exercise(monkeypatch, [b"12345", b"6789", b"unread"],
                                           headers=headers)
    assert sent[0]["status"] == 413
    assert incoming == calls == []
    assert reads == 2


@pytest.mark.parametrize("chunks", [[b"12", b"34"], [b"1234", b"5678"], [b""]])
def test_allowed_body_forwarded_exactly_once(monkeypatch, chunks):
    sent, incoming, calls, _ = exercise(monkeypatch, chunks)
    assert sent[0]["status"] == 204
    assert len(calls) == 1
    assert incoming == [
        {"type": "http.request", "body": b"".join(chunks), "more_body": False},
        {"type": "http.disconnect"},
    ]


def test_unrelated_route_preserves_original_stream(monkeypatch):
    sent, incoming, calls, _ = exercise(monkeypatch, [b"123456", b"789012"],
                                       path="/api/v1/other", headers=[(b"content-length", b"12")])
    assert sent[0]["status"] == 204
    assert len(calls) == 1
    assert incoming == [
        {"type": "http.request", "body": b"123456", "more_body": True},
        {"type": "http.request", "body": b"789012", "more_body": False},
        {"type": "http.disconnect"},
    ]
