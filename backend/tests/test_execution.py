import asyncio
from threading import Event

import pytest
from app.execution import BlockingRunner, PipelineBusy


def test_timeout_keeps_capacity_until_actual_work_finishes():
    runner = BlockingRunner(1)
    started, release, finished = Event(), Event(), Event()

    def block():
        started.set()
        try:
            assert release.wait(5)
        finally:
            finished.set()
        return "done"

    async def scenario():
        try:
            with pytest.raises(TimeoutError):
                await runner.run(block, timeout=0.02)
            assert started.is_set() and not finished.is_set()
            with pytest.raises(PipelineBusy):
                await runner.run(lambda: "must not run", timeout=1)
        finally:
            release.set()
        while not finished.is_set():
            await asyncio.sleep(0)
        # Completion callbacks may run immediately after the function returns.
        for _ in range(100):
            try:
                assert await runner.run(lambda: "recovered", timeout=1) == "recovered"
                return
            except PipelineBusy:
                await asyncio.sleep(0.001)
        pytest.fail("Worker capacity was not restored")

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        runner.close()


def test_cancelled_waiter_does_not_cancel_or_release_blocking_work():
    runner = BlockingRunner(1)
    started, release = Event(), Event()

    def block():
        started.set()
        assert release.wait(5)
        raise RuntimeError("private late provider exception")

    async def scenario():
        task = asyncio.create_task(runner.run(block, timeout=5))
        try:
            while not started.is_set():
                await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(PipelineBusy):
                await runner.run(lambda: None, timeout=1)
        finally:
            release.set()
        await asyncio.sleep(0.02)
        assert await runner.run(lambda: "recovered", timeout=1) == "recovered"

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        runner.close()


def test_worker_failure_and_submit_failure_restore_capacity():
    runner = BlockingRunner(1)

    def fail():
        raise RuntimeError("failure")

    async def scenario():
        with pytest.raises(RuntimeError):
            await runner.run(fail, timeout=1)
        assert await runner.run(lambda: 42, timeout=1) == 42
        runner.close()
        # Submission after shutdown fails, but must not leak admission capacity.
        for _ in range(2):
            with pytest.raises(RuntimeError, match="shutdown"):
                await runner.run(lambda: None, timeout=1)

    asyncio.run(scenario())


@pytest.mark.parametrize("capacity", [0, 9, True, 1.5])
def test_invalid_worker_capacity(capacity):
    with pytest.raises(ValueError):
        BlockingRunner(capacity)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_does_not_submit_work(timeout):
    runner = BlockingRunner(1)
    try:
        with pytest.raises(ValueError):
            asyncio.run(
                runner.run(lambda: pytest.fail("Must not run"), timeout=timeout)
            )
    finally:
        runner.close()
