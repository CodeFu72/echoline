# app/utils/mailer.py
from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8000")
MAIL_FROM = os.getenv("MAIL_FROM", "no-reply@localhost")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_TLS = os.getenv("SMTP_TLS", "1") not in ("0", "false", "False")

def _send_smtp(msg: EmailMessage) -> None:
    if not SMTP_HOST:
        # Dev fallback: print to console
        print("\n=== DEV EMAIL (SMTP not configured) ===")
        print(msg)
        print("=== /DEV EMAIL ===\n")
        return
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        if SMTP_TLS:
            s.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)

def send_password_reset_email(to_email: str, reset_url: str, *, sender: Optional[str] = None) -> None:
    sender = sender or MAIL_FROM
    subject = "Reset your Echo Line password"
    body = (
        f"Hi,\n\n"
        f"We received a request to reset your Echo Line password.\n"
        f"Click the link below to set a new password:\n\n"
        f"{reset_url}\n\n"
        f"If you didn’t request this, you can ignore this email.\n\n"
        f"— Echo Line"
    )
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    _send_smtp(msg)