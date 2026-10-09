"""Shared HTTP-level fakes for provider tests: real SDK clients over httpx.MockTransport."""

import json
from collections.abc import Callable, Iterator

import httpx
import pytest

Handler = Callable[[httpx.Request], httpx.Response]


class _BrokenStream(httpx.SyncByteStream):
    """Yields the given bytes, then fails like a dropped connection."""

    def __init__(self, first: bytes) -> None:
        self._first = first

    def __iter__(self) -> Iterator[bytes]:
        yield self._first
        raise httpx.ReadError("connection reset by peer")


def anthropic_sse(*texts: str) -> bytes:
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg",
                "type": "message",
                "role": "assistant",
                "model": "m",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        *[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t}}
            for t in texts
        ],
    ]
    return b"".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode() for event in events
    )


def anthropic_sse_complete(*texts: str, stop_reason: str = "end_turn") -> bytes:
    tail = [
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 1},
        },
        {"type": "message_stop"},
    ]
    return anthropic_sse(*texts) + b"".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode() for event in tail
    )


def openai_sse(*texts: str, finish_reason: str | None = "stop") -> bytes:
    chunks = [
        {
            "id": "c",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "m",
            "choices": [{"index": 0, "delta": {"content": t}, "finish_reason": None}],
        }
        for t in texts
    ]
    if finish_reason:
        chunks.append(
            {
                "id": "c",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "m",
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            }
        )
    body = b"".join(f"data: {json.dumps(c)}\n\n".encode() for c in chunks)
    return body + b"data: [DONE]\n\n"


def sse_response(body: bytes) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)


def broken_sse_response(first: bytes) -> httpx.Response:
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=_BrokenStream(first)
    )


def error_response(status: int, message: str = "error") -> httpx.Response:
    return httpx.Response(
        status, json={"type": "error", "error": {"type": "x", "message": message}}
    )


def raising(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


@pytest.fixture
def http_client() -> Callable[[Handler], httpx.Client]:
    return lambda handler: httpx.Client(transport=httpx.MockTransport(handler))
