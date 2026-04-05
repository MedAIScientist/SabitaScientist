"""Register PM slash commands."""
from __future__ import annotations

from ..manager import manager
from ..pm_commands import ProjectCommand, TaskCommand, UserCommand

manager.register(ProjectCommand())
manager.register(TaskCommand())
manager.register(UserCommand())
