"""Bound actual blocking work, even after the caller times out or disconnects."""

import asyncio
import math
import os
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore


class PipelineBusy(Exception):
    pass


class BlockingRunner:
    def __init__(self, capacity: int = 2):
        if type(capacity) is not int or not 1 <= capacity <= 8:
            raise ValueError("Worker capacity must be between 1 and 8.")
        self.capacity = capacity
        self._slots = BoundedSemaphore(capacity)
        self._executor = ThreadPoolExecutor(
            max_workers=capacity, thread_name_prefix="voice-adapter"
        )

    async def run(self, function, *args, timeout: float):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Adapter timeout must be finite and greater than zero.")
        if not self._slots.acquire(blocking=False):
            raise PipelineBusy(
                "Voice adapter capacity is busy. Retry after active work finishes."
            )
        try:
            work = self._executor.submit(function, *args)
        except BaseException:
            self._slots.release()
            raise
        # Release on actual worker completion, never on the timeout of its async waiter.
        work.add_done_callback(lambda _: self._slots.release())
        waiting = asyncio.wrap_future(work)
        # Consume late errors after a timeout without logging provider payloads.
        waiting.add_done_callback(
            lambda future: None if future.cancelled() else future.exception()
        )
        return await asyncio.wait_for(asyncio.shield(waiting), timeout=timeout)

    def close(self):
        self._executor.shutdown(wait=True, cancel_futures=True)


runner = BlockingRunner(int(os.getenv("VOICE_MAX_WORKERS", "2")))
