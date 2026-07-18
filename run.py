"""Run the bot polling + FastAPI face server in ONE asyncio event loop.

Both processes share the in-memory `state._GROUPS` module singleton, so the
Mini App always reads what the bot most-recently wrote — no IPC needed.

Usage:
  python run.py                          # binds 0.0.0.0:8000
  PORT=8765 python run.py                # override port
  PUBLIC_WEBAPP_URL=https://xxx.trycloudflare.com python run.py
"""
from __future__ import annotations
import asyncio
import contextlib
import logging
import os
import signal

import uvicorn
from dotenv import load_dotenv
from telegram import Update

import bot           # keep the bot.py logic untouched — just call build_app()
from api import app as fastapi_app


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("trippet.run")


async def _run_bot() -> None:
    """Initialize + start polling without .run_polling() (which owns its own loop).

    Wrapped in a retry loop so a transient Telegram TimedOut on startup doesn't
    take the whole process down. Once started, the updater's internal loop
    handles its own retries."""
    while True:
        app = bot.build_app()
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                bootstrap_retries=-1,     # infinite retries during startup
                drop_pending_updates=True,
            )
            log.info("bot: polling started")
            await asyncio.Event().wait()  # block until cancelled
        except asyncio.CancelledError:
            log.info("bot: cancelled, shutting down")
            with contextlib.suppress(Exception):
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            raise
        except Exception as e:
            log.warning("bot: crashed (%s: %s) — restarting in 5s", type(e).__name__, e)
            with contextlib.suppress(Exception):
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            await asyncio.sleep(5)


async def _run_api(port: int) -> None:
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    log.info("api: serving on 0.0.0.0:%d", port)
    await server.serve()


async def _main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    tasks = [
        asyncio.create_task(_run_bot(), name="bot"),
        asyncio.create_task(_run_api(port), name="api"),
    ]

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # windows

    await asyncio.wait([*tasks, asyncio.create_task(stop.wait())],
                       return_when=asyncio.FIRST_COMPLETED)
    for t in tasks:
        if not t.done():
            t.cancel()
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception) as e:
            if not isinstance(e, asyncio.CancelledError):
                log.exception("task exit: %s", e)


if __name__ == "__main__":
    asyncio.run(_main())
