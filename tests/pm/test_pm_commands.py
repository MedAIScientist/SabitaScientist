"""Tests for PM slash commands with mocked httpx."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from EvoScientist.commands.pm_commands import ProjectCommand, TaskCommand


@pytest.fixture
def ctx():
    ui = MagicMock()
    ui.append_system = MagicMock()
    ui.flush = AsyncMock()
    return MagicMock(ui=ui)


@pytest.fixture
def mock_server_running():
    with patch("EvoScientist.commands.pm_commands._ensure_server") as m:
        m.return_value = None
        yield m


@pytest.mark.asyncio
async def test_project_list_calls_api(ctx, mock_server_running) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": "p1", "name": "Alpha", "archived_at": None}]

    with patch("EvoScientist.commands.pm_commands._get", return_value=mock_response):
        cmd = ProjectCommand()
        await cmd.execute(ctx, ["list"])

    ctx.ui.append_system.assert_called()
    call_args = ctx.ui.append_system.call_args[0][0]
    assert "Alpha" in call_args


@pytest.mark.asyncio
async def test_task_list_no_active_project(ctx, mock_server_running) -> None:
    cmd = TaskCommand()
    # When no active project is set, should show an error
    with patch("EvoScientist.commands.pm_commands._active_project_id", None):
        await cmd.execute(ctx, ["list"])
    ctx.ui.append_system.assert_called()
    msg = ctx.ui.append_system.call_args[0][0]
    assert "project" in msg.lower()


@pytest.mark.asyncio
async def test_task_add_requires_title(ctx, mock_server_running) -> None:
    cmd = TaskCommand()
    with patch("EvoScientist.commands.pm_commands._active_project_id", "p1"):
        await cmd.execute(ctx, ["add"])  # no title
    ctx.ui.append_system.assert_called()
    msg = ctx.ui.append_system.call_args[0][0]
    assert "title" in msg.lower()
