"""Compute backend abstraction — SLURM, local, SSH, and cloud backends."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComputeResource:
    id: str
    name: str
    backend_type: str          # local | ssh | slurm | aws_batch | gcp
    config: dict[str, Any] = field(default_factory=dict)
    status: str = "unknown"    # unknown | online | offline | error
    created_at: str = ""


class ComputeBackend(ABC):
    """Abstract base for compute execution backends."""

    @abstractmethod
    async def submit_job(self, resource: ComputeResource, command: str, work_dir: str | None = None, env: dict | None = None) -> str:
        """Submit a command as a job. Returns job_id."""

    @abstractmethod
    async def get_job_status(self, job_id: str) -> str:
        """Return job status: pending | running | done | failed | cancelled."""

    @abstractmethod
    async def get_job_output(self, job_id: str) -> str:
        """Return job stdout/stderr."""

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""


class LocalBackend(ComputeBackend):
    """Executes commands directly on the local machine."""

    async def submit_job(self, resource: ComputeResource, command: str, work_dir: str | None = None, env: dict | None = None) -> str:
        job_id = f"local-{datetime.now(UTC).timestamp():.0f}"
        log_dir = Path(work_dir or "/tmp") / "compute-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{job_id}.log"
        full_env = {**os.environ, **(env or {})}
        cmd = f"cd {shlex.quote(work_dir or '.')} && {command} > {shlex.quote(str(log_file))} 2>&1 & echo $!"
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=full_env)
        pid = proc.stdout.strip()
        logger.info("Local job %s started (PID %s): %s", job_id, pid, command[:100])
        return job_id

    async def get_job_status(self, job_id: str) -> str:
        return "done"

    async def get_job_output(self, job_id: str) -> str:
        log_dir = Path("/tmp") / "compute-logs"
        log_file = log_dir / f"{job_id}.log"
        if log_file.exists():
            return log_file.read_text()[-10000:]
        return "No output"

    async def cancel_job(self, job_id: str) -> bool:
        return True


class SSHBackend(ComputeBackend):
    """Executes commands on a remote machine via SSH."""

    async def _ssh(self, host: str, command: str, key_file: str | None = None) -> tuple[int, str]:
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
        if key_file:
            cmd += ["-i", key_file]
        cmd += [host, command]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout

    async def submit_job(self, resource: ComputeResource, command: str, work_dir: str | None = None, env: dict | None = None) -> str:
        cfg = resource.config
        host = cfg.get("host", "localhost")
        user = cfg.get("user", "root")
        key_file = cfg.get("key_file")
        remote_host = f"{user}@{host}"

        env_str = " ".join(f"{k}={shlex.quote(v)}" for k, v in (env or {}).items())
        full_cmd = f"cd {shlex.quote(work_dir or '~')} && {env_str} nohup {command} > job.log 2>&1 & echo $!"
        _rc, _out = await self._ssh(remote_host, full_cmd, key_file)
        job_id = f"ssh-{host}-{datetime.now(UTC).timestamp():.0f}"
        logger.info("SSH job %s submitted to %s: %s", job_id, host, command[:80])
        return job_id

    async def get_job_status(self, job_id: str) -> str:
        return "running"

    async def get_job_output(self, job_id: str) -> str:
        return "SSH output not yet available"

    async def cancel_job(self, job_id: str) -> bool:
        return True


class SLURMBackend(ComputeBackend):
    """Submits jobs to a SLURM cluster."""

    async def _run(self, cmd: list[str]) -> tuple[int, str]:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout

    async def submit_job(self, resource: ComputeResource, command: str, work_dir: str | None = None, env: dict | None = None) -> str:
        cfg = resource.config
        partition = cfg.get("partition", "")
        account = cfg.get("account", "")
        nodes = cfg.get("nodes", 1)
        cpus = cfg.get("cpus", 1)
        mem = cfg.get("mem", "4G")
        time_limit = cfg.get("time", "01:00:00")

        script = "#!/bin/bash\n"
        script += "#SBATCH --job-name=evosci-job\n"
        script += f"#SBATCH --nodes={nodes}\n"
        script += f"#SBATCH --cpus-per-task={cpus}\n"
        script += f"#SBATCH --mem={mem}\n"
        script += f"#SBATCH --time={time_limit}\n"
        if partition:
            script += f"#SBATCH --partition={partition}\n"
        if account:
            script += f"#SBATCH --account={account}\n"
        script += "#SBATCH --output=slurm-%j.out\n"
        script += f"cd {shlex.quote(work_dir or '.')}\n"
        for k, v in (env or {}).items():
            script += f"export {k}={shlex.quote(v)}\n"
        script += f"{command}\n"

        script_path = Path(work_dir or "/tmp") / "slurm_script.sh"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(script)

        rc, out = await self._run(["sbatch", str(script_path)])
        if rc != 0:
            logger.error("SLURM submission failed: %s", out)
            raise RuntimeError(f"SLURM submission failed: {out}")

        job_id = out.strip().split()[-1]
        logger.info("SLURM job %s submitted: %s", job_id, command[:80])
        return job_id

    async def get_job_status(self, job_id: str) -> str:
        rc, out = await self._run(["sacct", "-j", job_id, "--format=State", "--noheader", "-P"])
        if rc != 0:
            return "unknown"
        state = out.strip().split("\n")[0] if out.strip() else "unknown"
        state_map = {
            "PENDING": "pending", "RUNNING": "running", "COMPLETED": "done",
            "FAILED": "failed", "CANCELLED": "cancelled", "TIMEOUT": "failed",
        }
        return state_map.get(state.upper(), state.lower())

    async def get_job_output(self, job_id: str) -> str:
        rc, out = await self._run(["cat", f"slurm-{job_id}.out"])
        return out[-10000:] if rc == 0 else "No output"

    async def cancel_job(self, job_id: str) -> bool:
        rc, _ = await self._run(["scancel", job_id])
        return rc == 0


_BACKENDS: dict[str, type[ComputeBackend]] = {
    "local": LocalBackend,
    "ssh": SSHBackend,
    "slurm": SLURMBackend,
}


def get_backend(backend_type: str) -> ComputeBackend:
    cls = _BACKENDS.get(backend_type)
    if not cls:
        raise ValueError(f"Unknown backend type: {backend_type}. Available: {list(_BACKENDS.keys())}")
    return cls()
