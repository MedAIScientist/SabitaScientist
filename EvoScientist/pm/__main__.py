"""Run the PM server: ``python -m EvoScientist.pm [--host H] [--port P]``.

Starts the API + SPA on ``--port`` and the AI runner on ``--runner-port``
(loopback only), without loading the rest of the EvoScientist package.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import threading

import uvicorn


def serve(host: str = "127.0.0.1", port: int = 7860, runner_port: int = 8001) -> None:
    from .api.app import create_app
    from .runner.main import create_runner_app

    runner = uvicorn.Server(
        uvicorn.Config(create_runner_app(), host="127.0.0.1", port=runner_port, log_level="error")
    )
    threading.Thread(target=lambda: asyncio.run(runner.serve()), daemon=True).start()
    os.environ.setdefault("PM_RUNNER_URL", f"http://127.0.0.1:{runner_port}")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m EvoScientist.pm")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--runner-port", type=int, default=8001)
    args = parser.parse_args()
    serve(args.host, args.port, args.runner_port)


if __name__ == "__main__":
    main()
