"""Email notification system for PM events — task assignments, admissions, publications."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from .settings import get_smtp_config

logger = logging.getLogger(__name__)

_SMTP = get_smtp_config()


def is_configured() -> bool:
    cfg = get_smtp_config()
    return bool(cfg["host"] and cfg["user"])


def send_email(to: str, subject: str, body: str) -> bool:
    cfg = get_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        logger.warning("Email not configured — skipped notification to %s", to)
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg["from_addr"]
        msg["To"] = to
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            if cfg["use_tls"]:
                s.starttls()
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def notify_task_assignment(
    to_email: str, task_title: str, project_name: str, task_id: str, assigned_by: str
) -> None:
    cfg = get_smtp_config()
    send_email(
        to_email,
        f"[Gazzali] Task assigned: {task_title}",
        f"You have been assigned a task in the project '{project_name}' by {assigned_by}.\n\n"
        f"Title: {task_title}\n"
        f"Link: {cfg['base_url']}/projects/{task_id.split('-')[0] if '-' in task_id else task_id}\n",
    )


def notify_admission_review(
    to_email: str, applicant_name: str, admission_id: str
) -> None:
    cfg = get_smtp_config()
    send_email(
        to_email,
        f"[Gazzali] New admission: {applicant_name}",
        f"A new admission application requires review.\n\n"
        f"Applicant: {applicant_name}\n"
        f"Link: {cfg['base_url']}/admissions/{admission_id}\n",
    )


def notify_publication_status(
    to_email: str, pub_title: str, new_status: str, pub_id: str
) -> None:
    cfg = get_smtp_config()
    send_email(
        to_email,
        f"[Gazzali] Publication '{pub_title[:60]}' is now {new_status}",
        f"Publication status changed to {new_status}.\n\n"
        f"Title: {pub_title}\n"
        f"Link: {cfg['base_url']}/publications/{pub_id}\n",
    )
