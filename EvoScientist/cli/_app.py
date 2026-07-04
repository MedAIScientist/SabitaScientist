"""Typer application objects — no intra-package imports to avoid circular deps."""
from __future__ import annotations

import typer  # type: ignore[import-untyped]

app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Config subcommand group
config_app = typer.Typer(
    help="Configuration management commands", invoke_without_command=True
)
app.add_typer(config_app, name="config")

# MCP subcommand group
_MCP_HELP = """\
Configure and manage MCP servers

Examples:
  # Add a local MCP server (stdio auto-detected):
  EvoSci mcp add local-server python -- /path/to/server.py

  # Add an npx-based server:
  EvoSci mcp add sequential-thinking npx -- -y @modelcontextprotocol/server-sequential-thinking

  # Add an HTTP server (http auto-detected from URL):
  EvoSci mcp add docs-langchain https://docs.langchain.com/mcp

  # Add a stdio server with env vars (hardcoded):
  EvoSci mcp add my-server node --env API_KEY=xxx -- server.js

  # Add a server with runtime env ref (resolved from .env at startup):
  EvoSci mcp add brave-search npx --env-ref BRAVE_API_KEY -- -y @modelcontextprotocol/server-brave-search

  # Expose to a specific sub-agent (e.g. research-agent):
  EvoSci mcp add brave-search npx --env-ref BRAVE_API_KEY -e research-agent -- -y @modelcontextprotocol/server-brave-search

  # Expose to multiple agents:
  EvoSci mcp add local-server python -e main,research-agent,code-agent -- /path/to/server.py

  # Explicit transport override:
  EvoSci mcp add my-sse https://example.com/sse --transport sse

Sub-agents (-e): planner-agent | research-agent | code-agent | debug-agent | data-analysis-agent | writing-agent
"""
mcp_app = typer.Typer(help=_MCP_HELP, invoke_without_command=True)
app.add_typer(mcp_app, name="mcp")

# Channel subcommand group
channel_app = typer.Typer(help="Channel management commands")
app.add_typer(channel_app, name="channel")


# Sessions subcommand group — diagnostic tools for the LangGraph checkpoint DB
sessions_app = typer.Typer(
    help="Inspect and manage the sessions DB (~/.evoscientist/sessions.db)",
    invoke_without_command=True,
)
app.add_typer(sessions_app, name="sessions")

# Configure subcommand group — re-run a single onboarding section.
configure_app = typer.Typer(
    help=(
        "Re-run one onboarding section without going through the full wizard.\n"
        "Example: EvoSci configure provider"
    ),
)
app.add_typer(configure_app, name="configure")


@app.command()
def dashboard(
    port: int = typer.Option(7860, "--port", help="Port to run the PM server on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the PM server to"),
    runner_port: int = typer.Option(8001, "--runner-port", help="Port for the runner service"),
    open: bool = typer.Option(True, "--open/--no-open", help="Open browser after starting"),
) -> None:
    """Start the project management dashboard (+ EvoScientist runner service)."""
    import os
    import threading

    import uvicorn

    from EvoScientist.pm.api.app import create_app
    from EvoScientist.pm.runner.main import create_runner_app

    # Start runner service in a background daemon thread
    runner_server = uvicorn.Server(
        uvicorn.Config(
            create_runner_app(),
            host="127.0.0.1",
            port=runner_port,
            log_level="error",
        )
    )

    def _start_runner() -> None:
        import asyncio
        asyncio.run(runner_server.serve())

    runner_thread = threading.Thread(target=_start_runner, daemon=True)
    runner_thread.start()

    # Tell PM backend where the runner lives
    os.environ["RUNNER_URL"] = f"http://127.0.0.1:{runner_port}"

    if open:
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
