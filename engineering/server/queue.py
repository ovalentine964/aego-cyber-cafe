"""
queue.py — Async request queue for Ollama LLM calls.

The LLM can only handle one request at a time. This queue:
- Processes requests FIFO with priority (voice > text)
- Sends progress notifications via callback
- Handles timeouts (60s default)
- Retries once on Ollama failure

Designed for Raspberry Pi 5 — minimal memory overhead.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("aego.queue")


class Priority(IntEnum):
    """Lower value = higher priority."""
    VOICE = 0
    TEXT = 1
    BACKGROUND = 2


@dataclass
class QueueItem:
    """A single request in the queue."""
    request_id: str
    priority: Priority
    handler: Callable[..., Awaitable[Any]]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    timeout: float = 60.0
    max_retries: int = 1
    on_progress: Optional[Callable[[str], Awaitable[None]]] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class QueueResult:
    """Result of a queued request."""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    elapsed: float = 0.0
    retries: int = 0


class RequestQueue:
    """
    Async priority queue for Ollama requests.

    Usage:
        queue = RequestQueue()
        asyncio.create_task(queue.run())

        result = await queue.enqueue(
            request_id="req-123",
            priority=Priority.TEXT,
            handler=some_async_function,
            args=(arg1,),
            kwargs={"key": "val"},
        )
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 1,
    ):
        self._queue: asyncio.PriorityQueue[
            tuple[int, float, QueueItem]
        ] = asyncio.PriorityQueue()
        self._pending: dict[str, asyncio.Future[QueueResult]] = {}
        self._running = False
        self._processing = False
        self._default_timeout = timeout
        self._default_max_retries = max_retries
        self._current_item: Optional[QueueItem] = None

    async def enqueue(
        self,
        request_id: str,
        priority: Priority,
        handler: Callable[..., Awaitable[Any]],
        args: tuple = (),
        kwargs: dict | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> QueueResult:
        """
        Enqueue a request and wait for its result.

        Returns QueueResult when the request has been processed.
        """
        item = QueueItem(
            request_id=request_id,
            priority=priority,
            handler=handler,
            args=args,
            kwargs=kwargs or {},
            timeout=timeout or self._default_timeout,
            max_retries=max_retries if max_retries is not None else self._default_max_retries,
            on_progress=on_progress,
        )

        future: asyncio.Future[QueueResult] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        # Priority queue sorts by (priority_value, timestamp, item)
        # Lower priority value = processed first; earlier timestamp = FIFO within same priority
        await self._queue.put((item.priority.value, item.created_at, item))

        logger.info(
            f"Enqueued: {request_id} (priority={priority.name}, "
            f"queue_size={self._queue.qsize()})"
        )

        try:
            return await asyncio.wait_for(future, timeout=item.timeout + 10)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            return QueueResult(
                request_id=request_id,
                success=False,
                error="Request timed out in queue",
                elapsed=item.timeout + 10,
            )

    async def run(self) -> None:
        """Main queue processing loop. Run as a background task."""
        self._running = True
        logger.info("Request queue started")

        while self._running:
            try:
                # Wait for next item with timeout to allow shutdown checks
                try:
                    priority, ts, item = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                self._processing = True
                self._current_item = item
                result = await self._process_item(item)
                self._current_item = None
                self._processing = False

                # Resolve the caller's future
                future = self._pending.pop(item.request_id, None)
                if future and not future.done():
                    future.set_result(result)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}", exc_info=True)
                self._processing = False

        logger.info("Request queue stopped")

    async def _process_item(self, item: QueueItem) -> QueueResult:
        """Process a single queue item with retries and timeout."""
        start = time.time()
        retries = 0

        # Notify: started
        if item.on_progress:
            try:
                await item.on_progress("Processing your request...")
            except Exception:
                pass

        while retries <= item.max_retries:
            try:
                result = await asyncio.wait_for(
                    item.handler(*item.args, **item.kwargs),
                    timeout=item.timeout,
                )
                elapsed = time.time() - start
                logger.info(
                    f"Completed: {item.request_id} "
                    f"(elapsed={elapsed:.1f}s, retries={retries})"
                )
                return QueueResult(
                    request_id=item.request_id,
                    success=True,
                    result=result,
                    elapsed=elapsed,
                    retries=retries,
                )

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout: {item.request_id} "
                    f"(attempt {retries + 1}, timeout={item.timeout}s)"
                )
                return QueueResult(
                    request_id=item.request_id,
                    success=False,
                    error=f"Request timed out after {item.timeout}s",
                    elapsed=time.time() - start,
                    retries=retries,
                )

            except Exception as e:
                retries += 1
                logger.warning(
                    f"Error: {item.request_id} attempt {retries}: {e}"
                )
                if retries <= item.max_retries:
                    if item.on_progress:
                        try:
                            await item.on_progress(
                                f"Retrying... (attempt {retries + 1})"
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    return QueueResult(
                        request_id=item.request_id,
                        success=False,
                        error=str(e),
                        elapsed=time.time() - start,
                        retries=retries - 1,
                    )

        # Should not reach here, but just in case
        return QueueResult(
            request_id=item.request_id,
            success=False,
            error="Max retries exceeded",
            elapsed=time.time() - start,
            retries=retries,
        )

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        return self._processing

    def status(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "processing": self._processing,
            "current_request": (
                self._current_item.request_id
                if self._current_item else None
            ),
            "pending_count": len(self._pending),
        }

    async def shutdown(self) -> None:
        """Gracefully stop the queue."""
        self._running = False
        # Cancel any pending futures
        for req_id, future in self._pending.items():
            if not future.done():
                future.set_result(QueueResult(
                    request_id=req_id,
                    success=False,
                    error="Server shutting down",
                ))
        self._pending.clear()
