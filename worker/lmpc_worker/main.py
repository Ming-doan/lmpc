"""Worker entry point with graceful shutdown."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

import structlog

from lmpc_worker.client import BackendClient
from lmpc_worker.config import settings
from lmpc_worker.registration import register_or_load, wait_for_approval


def _configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LMPC_LOG_LEVEL.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LMPC_LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


log = structlog.get_logger()


async def _run() -> None:
    token = await register_or_load()
    client = BackendClient(token)
    await wait_for_approval(client)

    shutdown = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        log.info("worker.shutdown_requested", signal=sig.name)
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            # Windows fallback
            signal.signal(sig, lambda s, f: shutdown.set())

    from lmpc_worker.poller import run_poll_loop
    log.info("worker.started", name=settings.LMPC_WORKER_NAME)

    try:
        await run_poll_loop(client, shutdown)
    finally:
        await client.aclose()
        log.info("worker.stopped")


def main() -> None:
    _configure_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
