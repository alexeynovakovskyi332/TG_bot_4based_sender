import asyncio
import threading

stop_event_async = asyncio.Event()
stop_event_thread = threading.Event()