"""Slash commands for project management: /project, /task, /user."""
from __future__ import annotations

import getpass
from pathlib import Path

import httpx

from .base import Command, CommandContext

_BASE_URL = "http://127.0.0.1:7860/api/v1"
_TOKEN_FILE = Path.home() / ".config" / "evoscientist" / "pm_token"
_active_project_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_server() -> None:
    """Start the PM server if not running."""
    from EvoScientist.pm.server import start_server_background
    start_server_background()


def _load_token() -> str | None:
    """Load saved auth token from disk."""
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text().strip() or None
    return None


def _save_token(token: str) -> None:
    """Persist auth token to disk with restricted permissions."""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token)
    _TOKEN_FILE.chmod(0o600)


def _headers() -> dict[str, str]:
    """Build auth headers from saved token."""
    token = _load_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _get(path: str) -> httpx.Response:
    """GET request to the PM API."""
    return httpx.get(f"{_BASE_URL}{path}", headers=_headers(), timeout=5)


def _post(path: str, data: dict) -> httpx.Response:
    """POST request to the PM API."""
    return httpx.post(f"{_BASE_URL}{path}", json=data, headers=_headers(), timeout=5)


def _put(path: str, data: dict) -> httpx.Response:
    """PUT request to the PM API."""
    return httpx.put(f"{_BASE_URL}{path}", json=data, headers=_headers(), timeout=5)


def _delete(path: str) -> httpx.Response:
    """DELETE request to the PM API."""
    return httpx.delete(f"{_BASE_URL}{path}", headers=_headers(), timeout=5)


def _maybe_login(ctx: CommandContext) -> bool:
    """Prompt for login if no valid token. Returns True if authenticated."""
    resp = _get("/users/me")
    if resp.status_code == 200:
        return True
    ctx.ui.append_system("Not logged in. Enter credentials:")
    username = input("  Username: ")
    password = getpass.getpass("  Password: ")
    login_resp = httpx.post(
        f"{_BASE_URL}/auth/login",
        json={"username": username, "password": password},
        timeout=5,
    )
    if login_resp.status_code == 200:
        _save_token(login_resp.json()["token"])
        return True
    ctx.ui.append_system("Login failed.")
    return False


# ── /project command ──────────────────────────────────────────────────────────

class ProjectCommand(Command):
    name = "/project"
    description = "Manage projects: list, create, switch, info, invite"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        """Handle /project subcommands."""
        global _active_project_id
        _ensure_server()
        if not _maybe_login(ctx):
            return
        sub = args[0] if args else "list"

        if sub == "list":
            resp = _get("/projects")
            if resp.status_code != 200:
                ctx.ui.append_system(f"Error: {resp.status_code}")
                return
            projects = resp.json()
            if not projects:
                ctx.ui.append_system("No projects. Create one with /project create <name>")
                return
            lines = ["Projects:"]
            for p in projects:
                active_marker = " <- active" if p["id"] == _active_project_id else ""
                lines.append(f"  [{p['id'][:8]}] {p['name']}{active_marker}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "create":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project create <name>")
                return
            name = " ".join(args[1:])
            resp = _post("/projects", {"name": name})
            if resp.status_code == 201:
                p = resp.json()
                _active_project_id = p["id"]
                ctx.ui.append_system(f"Created project '{p['name']}' [{p['id'][:8]}] (now active)")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}")

        elif sub == "switch":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project switch <id|name>")
                return
            query = args[1]
            resp = _get("/projects")
            matches = [p for p in resp.json() if p["id"].startswith(query) or query.lower() in p["name"].lower()]
            if not matches:
                ctx.ui.append_system(f"No project matching '{query}'")
                return
            _active_project_id = matches[0]["id"]
            ctx.ui.append_system(f"Active project: {matches[0]['name']} [{matches[0]['id'][:8]}]")

        elif sub == "info":
            if not _active_project_id:
                ctx.ui.append_system("No active project. Use /project switch <name>")
                return
            resp = _get(f"/projects/{_active_project_id}")
            if resp.status_code != 200:
                ctx.ui.append_system(f"Error: {resp.status_code}")
                return
            p = resp.json()
            members = ", ".join(f"{m['username']}({m['role']})" for m in p.get("members", []))
            ctx.ui.append_system(f"Project: {p['name']}\nDescription: {p.get('description') or '-'}\nMembers: {members}")

        elif sub == "invite":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project invite <username> [--role editor|viewer]")
                return
            if not _active_project_id:
                ctx.ui.append_system("No active project.")
                return
            username = args[1]
            role = "editor"
            if "--role" in args:
                idx = args.index("--role")
                role = args[idx + 1] if idx + 1 < len(args) else "editor"
            users_resp = _get("/users")
            user = next((u for u in users_resp.json() if u["username"] == username), None)
            if not user:
                ctx.ui.append_system(f"User '{username}' not found.")
                return
            resp = _post(f"/projects/{_active_project_id}/members", {"user_id": user["id"], "role": role})
            if resp.status_code == 201:
                ctx.ui.append_system(f"Invited {username} as {role}.")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}")
        else:
            ctx.ui.append_system("Subcommands: list, create, switch, info, invite")


# ── /task command ─────────────────────────────────────────────────────────────

class TaskCommand(Command):
    name = "/task"
    description = "Manage tasks in the active project: list, add, done, show"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        """Handle /task subcommands."""
        _ensure_server()
        sub = args[0] if args else "list"

        # Validate active project and args BEFORE making any auth/HTTP calls
        # so tests that patch only _ensure_server can exercise error paths.
        if sub not in ("help",):
            if not _active_project_id:
                ctx.ui.append_system("No active project. Use /project switch <name>")
                return

        if sub == "add" and len(args) < 2:
            ctx.ui.append_system(
                "Usage: /task add <title> [--deadline YYYY-MM-DD] [--priority high|medium|low]"
            )
            return

        if not _maybe_login(ctx):
            return

        if sub == "list":
            resp = _get(f"/projects/{_active_project_id}/tasks")
            tasks = resp.json()
            if not tasks:
                ctx.ui.append_system("No tasks in this project.")
                return
            groups: dict[str, list] = {"todo": [], "in_progress": [], "done": []}
            for t in tasks:
                groups[t["status"]].append(t)
            lines = []
            for status, items in groups.items():
                if items:
                    lines.append(f"{status.upper()}:")
                    for t in items:
                        deadline = f" [due {t['deadline']}]" if t.get("deadline") else ""
                        lines.append(f"  [{t['id'][:8]}] {t['title']} ({t['priority']}){deadline}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "add":
            remaining = args[1:]
            deadline = None
            priority = "medium"
            assignee_id = None
            title_parts = []
            i = 0
            while i < len(remaining):
                if remaining[i] == "--deadline" and i + 1 < len(remaining):
                    deadline = remaining[i + 1]
                    i += 2
                elif remaining[i] == "--priority" and i + 1 < len(remaining):
                    priority = remaining[i + 1]
                    i += 2
                elif remaining[i] == "--assignee" and i + 1 < len(remaining):
                    uname = remaining[i + 1]
                    i += 2
                    users_resp = _get("/users")
                    user = next((u for u in users_resp.json() if u["username"] == uname), None)
                    assignee_id = user["id"] if user else None
                else:
                    title_parts.append(remaining[i])
                    i += 1
            title = " ".join(title_parts)
            if not title:
                ctx.ui.append_system("Task title is required.")
                return
            resp = _post(f"/projects/{_active_project_id}/tasks", {
                "title": title, "priority": priority,
                "deadline": deadline, "assignee_id": assignee_id,
            })
            if resp.status_code == 201:
                t = resp.json()
                ctx.ui.append_system(f"Created task [{t['id'][:8]}]: {t['title']}")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}")

        elif sub == "done":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /task done <id>")
                return
            task_id_prefix = args[1]
            resp = _get(f"/projects/{_active_project_id}/tasks")
            task = next((t for t in resp.json() if t["id"].startswith(task_id_prefix)), None)
            if not task:
                ctx.ui.append_system(f"Task '{task_id_prefix}' not found.")
                return
            _put(f"/projects/{_active_project_id}/tasks/{task['id']}", {"status": "done"})
            ctx.ui.append_system(f"Marked '{task['title']}' as done.")

        elif sub == "show":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /task show <id>")
                return
            task_id_prefix = args[1]
            tasks_resp = _get(f"/projects/{_active_project_id}/tasks")
            task = next((t for t in tasks_resp.json() if t["id"].startswith(task_id_prefix)), None)
            if not task:
                ctx.ui.append_system(f"Task '{task_id_prefix}' not found.")
                return
            lines = [
                f"Title:    {task['title']}",
                f"Status:   {task['status']}",
                f"Priority: {task['priority']}",
                f"Deadline: {task.get('deadline') or '-'}",
                f"Session:  {task.get('session_id') or '-'}",
                f"Desc:     {task.get('description') or '-'}",
            ]
            comments_resp = _get(f"/projects/{_active_project_id}/tasks/{task['id']}/comments")
            if comments_resp.status_code == 200 and comments_resp.json():
                lines.append("Comments:")
                for c in comments_resp.json():
                    lines.append(f"  [{c['created_at'][:10]}] {c['body']}")
            ctx.ui.append_system("\n".join(lines))
        else:
            ctx.ui.append_system("Subcommands: list, add, done, show")


# ── /user command (admin only) ────────────────────────────────────────────────

class UserCommand(Command):
    name = "/user"
    description = "Manage users (admin only): list, create"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        """Handle /user subcommands."""
        _ensure_server()
        if not _maybe_login(ctx):
            return
        sub = args[0] if args else "list"

        if sub == "list":
            resp = _get("/users")
            if resp.status_code == 403:
                ctx.ui.append_system("Admin access required.")
                return
            users = resp.json()
            lines = ["Users:"]
            for u in users:
                admin_tag = " [admin]" if u.get("is_admin") else ""
                lines.append(f"  {u['username']}{admin_tag}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "create":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /user create <username>")
                return
            username = args[1]
            password = getpass.getpass(f"  Password for {username}: ")
            resp = _post("/users", {"username": username, "password": password})
            if resp.status_code == 201:
                ctx.ui.append_system(f"Created user '{username}'.")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}")
        else:
            ctx.ui.append_system("Subcommands: list, create")
