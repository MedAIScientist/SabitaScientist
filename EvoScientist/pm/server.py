"""Helpers to start and stop the PM server as a background subprocess."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_PORT = 7860
_PID_FILE = Path.home() / ".config" / "evoscientist" / "pm.pid"


def is_server_running() -> bool:
    """Return True if the PM server is reachable on localhost:{_PORT}."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", _PORT)) == 0


def start_server_background() -> None:
    """Start the PM server as a background subprocess. No-op if already running."""
    if is_server_running():
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "EvoScientist.pm._run_server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(proc.pid))
    # Wait up to 3 seconds for the server to start
    for _ in range(12):
        if is_server_running():
            return
        time.sleep(0.25)


def stop_server() -> None:
    """Stop the background PM server if running."""
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
        _PID_FILE.unlink(missing_ok=True)
