import asyncio
import threading
from typing import Optional

# user_id -> (stop_async, stop_thread)
_sessions: dict[int, tuple[asyncio.Event, threading.Event]] = {}


def create_session(user_id: int) -> tuple[asyncio.Event, threading.Event]:
    stop_async = asyncio.Event()
    stop_thread = threading.Event()
    _sessions[user_id] = (stop_async, stop_thread)
    return stop_async, stop_thread


def get_session(user_id: int) -> Optional[tuple[asyncio.Event, threading.Event]]:
    return _sessions.get(user_id)


def remove_session(user_id: int) -> None:
    _sessions.pop(user_id, None)
