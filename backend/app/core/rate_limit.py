"""Small process-local fixed-window limiter for sensitive public lookups."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 15 * 60
_MAX_REQUESTS = 10
_events: dict[str, deque[float]] = defaultdict(deque)
_checkout_events: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()

_AUTH_WINDOW_SECONDS = 60
_AUTH_MAX_REQUESTS = 5
_auth_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def limit_auth_attempt(request: Request) -> None:
    """Allow five attempts per minute per IP and authentication endpoint."""
    client_ip = request.client.host if request.client else "unknown"
    key = (request.url.path, client_ip)
    now = time.monotonic()
    with _lock:
        events = _auth_events[key]
        while events and now - events[0] >= _AUTH_WINDOW_SECONDS:
            events.popleft()
        if len(events) >= _AUTH_MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please try again in one minute.",
                headers={"Retry-After": str(_AUTH_WINDOW_SECONDS)},
            )
        events.append(now)
        if len(_auth_events) > 10_000:
            expired = [bucket for bucket, values in _auth_events.items() if not values or now - values[-1] >= _AUTH_WINDOW_SECONDS]
            for bucket in expired:
                _auth_events.pop(bucket, None)


def limit_public_tracking(request: Request) -> None:
    """Allow ten order lookups per client address every fifteen minutes."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        events = _events[client_ip]
        while events and now - events[0] >= _WINDOW_SECONDS:
            events.popleft()
        if len(events) >= _MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many tracking attempts. Please try again later.",
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        events.append(now)

        # Bound memory when the service sees many one-off client addresses.
        if len(_events) > 10_000:
            expired = [key for key, bucket in _events.items() if not bucket or now - bucket[-1] >= _WINDOW_SECONDS]
            for key in expired:
                _events.pop(key, None)


def limit_guest_checkout(request: Request) -> None:
    """Allow ten guest orders per client address every fifteen minutes."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        events = _checkout_events[client_ip]
        while events and now - events[0] >= _WINDOW_SECONDS:
            events.popleft()
        if len(events) >= _MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many orders from this connection. Please try again later.",
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        events.append(now)
        if len(_checkout_events) > 10_000:
            expired = [key for key, bucket in _checkout_events.items() if not bucket or now - bucket[-1] >= _WINDOW_SECONDS]
            for key in expired:
                _checkout_events.pop(key, None)
