"""FastAPI application factory."""

import json
import re
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.config import settings

# ═══════════════════════════════════════════════════════════
# Fix: Pydantic v2 serializes Decimal → str like "123.45".
# The POS frontend calls .toFixed() on these values, which
# fails on strings. This middleware intercepts JSON responses
# and converts Decimal strings back to numbers.
#
# Regex matches JSON number-like strings (e.g., "123.45",
# "0.00", "5000.00") but NOT true strings like "DIESEL".
# We match quoted strings that look like numbers and remove
# the quotes around them.
# ═══════════════════════════════════════════════════════════

_DECIMAL_RE = re.compile(r'"(?:0|[1-9]\d*)(?:\.\d+)"')


def _fix_decimal_strings(body: bytes) -> bytes:
    """Replace all "123.45" strings in JSON with unquoted 123.45."""
    text = body.decode("utf-8", errors="replace")
    # Replace quoted number-like strings with bare numbers
    fixed = _DECIMAL_RE.sub(
        lambda m: m.group(0)[1:-1],  # strip surrounding quotes
        text,
    )
    return fixed.encode("utf-8")


class DecimalFixMiddleware:
    """ASGI middleware that converts Pydantic Decimal strings to JSON numbers."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_type: str = ""
        start_message: dict | None = None

        async def send_wrapper(message: dict) -> None:
            nonlocal content_type, start_message
            if message["type"] == "http.response.start":
                # Buffer the start message — we'll send it after modifying the body
                start_message = message
                for h in message.get("headers", []):
                    if h[0] == b"content-type":
                        content_type = h[1].decode("latin-1", errors="replace")
                        break
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if b"application/json" in content_type.encode():
                    body = _fix_decimal_strings(body)
                # Update Content-Length in the buffered start message
                if start_message is not None:
                    new_headers = []
                    for h in start_message.get("headers", []):
                        if h[0] != b"content-length":
                            new_headers.append(h)
                    new_headers.append((b"content-length", str(len(body)).encode()))
                    start_message = {**start_message, "headers": new_headers}
                    await send(start_message)
                    start_message = None
                await send({"type": "http.response.body", "body": body})
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(DecimalFixMiddleware)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version}
