"""MCP server management — browse marketplace, install, list, remove.

Integrates EvoScientist's ``mcp/registry`` and ``mcp/client`` so the PM
dashboard can manage Model Context Protocol servers without the CLI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("/mcp/marketplace")
def list_marketplace(
    tag: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """List available MCP servers from the EvoSkills marketplace.

    Uses ``fetch_marketplace_index()`` from EvoScientist.mcp.registry.
    Optionally filtered by tag. Cached for 10 minutes.
    """
    from ....mcp.registry import (
        fetch_marketplace_index,
        get_all_tags,
        get_installed_names,
    )

    installed = get_installed_names()
    servers = fetch_marketplace_index()

    if tag:
        servers = [s for s in servers if tag.lower() in {t.lower() for t in s.tags}]

    return {
        "servers": [
            {
                "name": s.name,
                "label": s.label,
                "description": s.description,
                "tags": s.tags,
                "transport": s.transport,
                "pip_package": s.pip_package,
                "env_key": s.env_key,
                "env_hint": s.env_hint,
                "env_optional": s.env_optional,
                "installed": s.name in installed,
            }
            for s in servers
        ],
        "tags": sorted(get_all_tags(servers)),
    }


@router.get("/mcp/installed")
def list_installed(
    current_user: User = Depends(get_current_user),
):
    """List currently installed MCP servers from the user's mcp.yaml.

    Uses ``_load_user_config()`` from EvoScientist.mcp.client.
    """
    from ....mcp.client import _load_user_config

    config = _load_user_config()
    return {
        "servers": [
            {
                "name": name,
                "transport": cfg.get("transport", "stdio"),
                "command": cfg.get("command"),
                "args": cfg.get("args", []),
                "url": cfg.get("url"),
            }
            for name, cfg in config.items()
        ]
    }


@router.post("/mcp/install", status_code=status.HTTP_201_CREATED)
def install_server(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Install an MCP server from the marketplace by name.

    Delegates to ``install_mcp_server()`` from EvoScientist.mcp.registry,
    which handles pip package installation and mcp.yaml persistence.
    """
    from ....mcp.registry import (
        fetch_marketplace_index,
        find_server_by_name,
        install_mcp_server,
    )

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    servers = fetch_marketplace_index()
    entry = find_server_by_name(name, servers)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server '{name}' not found in marketplace",
        )

    try:
        ok = install_mcp_server(entry)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Installation failed: {exc}"
        ) from exc

    if not ok:
        raise HTTPException(status_code=500, detail="Installation failed")

    return {"status": "installed", "name": entry.name, "transport": entry.transport}


@router.delete("/mcp/installed/{name}", status_code=status.HTTP_204_NO_CONTENT)
def remove_server(
    name: str,
    current_user: User = Depends(get_current_user),
):
    """Remove an installed MCP server from the user's mcp.yaml.

    Uses ``remove_mcp_server()`` from EvoScientist.mcp.client.
    """
    from ....mcp.client import _load_user_config, remove_mcp_server

    config = _load_user_config()
    if name not in config:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

    remove_mcp_server(name)
