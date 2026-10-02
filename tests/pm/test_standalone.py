"""The PM must run without the rest of the EvoScientist package."""

from __future__ import annotations

import subprocess
import sys


def test_pm_app_imports_no_evoscientist_core_module() -> None:
    # A fresh interpreter: other tests may already have imported the core.
    code = (
        "import sys\n"
        "from EvoScientist.pm.api.app import create_app\n"
        "from EvoScientist.pm.runner.main import create_runner_app\n"
        "import EvoScientist.pm.__main__\n"
        "core = sorted(m for m in sys.modules if m.startswith('EvoScientist.')"
        " and not m.startswith('EvoScientist.pm'))\n"
        "print('\\n'.join(core))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "", f"PM pulled in core modules:\n{out.stdout}"
