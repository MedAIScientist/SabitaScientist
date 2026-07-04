"""Email notification system for PM events — task assignments, admissions, publications."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("PM_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("PM_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("PM_SMTP_USER", "")
SMTP_PASS = os.environ.get("PM_SMTP_PASS", "")
SMTP_FROM = os.environ.get("PM_SMTP_FROM", "noreply@evoscientist.local")
BASE_URL = os.environ.get("PM_BASE_URL", "http://localhost:7860")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER)


def send_email(to: str, subject: str, body: str) -> bool:
    if not is_configured():
        logger.warning("Email not configured — skipped notification to %s", to)
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def notify_task_assignment(to_email: str, task_title: str, project_name: str, task_id: str, assigned_by: str) -> None:
    send_email(
        to_email,
        f"[EvoScientist] Task assigned: {task_title}",
        f"You have been assigned a task in the project '{project_name}' by {assigned_by}.\n\n"
        f"Title: {task_title}\n"
        f"Link: {BASE_URL}/projects/{task_id.split('-')[0] if '-' in task_id else task_id}\n"
    )


def notify_admission_review(to_email: str, applicant_name: str, admission_id: str) -> None:
    send_email(
        to_email,
        f"[EvoScientist] New admission: {applicant_name}",
        f"A new admission application requires review.\n\n"
        f"Applicant: {applicant_name}\n"
        f"Link: {BASE_URL}/admissions/{admission_id}\n"
    )


def notify_publication_status(to_email: str, pub_title: str, new_status: str, pub_id: str) -> None:
    send_email(
        to_email,
        f"[EvoScientist] Publication '{pub_title[:60]}' is now {new_status}",
        f"Publication status changed to {new_status}.\n\n"
        f"Title: {pub_title}\n"
        f"Link: {BASE_URL}/publications/{pub_id}\n"
    )
