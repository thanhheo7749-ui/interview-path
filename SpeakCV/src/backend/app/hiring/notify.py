import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.database.sql_models import Notification, User

logger = logging.getLogger(__name__)


def enqueue(db, company_id, user_id, kind, language, subject, body) -> Notification:
    """Add a pending notification. The caller commits."""
    row = Notification(company_id=company_id, user_id=user_id, kind=kind, language=language,
                       subject=subject, body=body, status="pending")
    db.add(row)
    db.flush()
    return row


def send_pending(db) -> int:
    """Send pending notifications by SMTP. Without SMTP_HOST nothing is sent (status stays in the app)."""
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return 0
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    username = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", "") or username or "no-reply@localhost"

    sent = 0
    rows = db.query(Notification).filter(Notification.status == "pending").order_by(Notification.id).all()
    for row in rows:
        user = db.get(User, row.user_id)
        if user is None or not user.email:
            continue
        message = EmailMessage()
        message["From"] = sender
        message["To"] = user.email
        message["Subject"] = row.subject
        message.set_content(row.body)
        try:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                if username:
                    smtp.starttls()
                    smtp.login(username, password)
                smtp.send_message(message)
        except Exception:
            logger.warning("Notification %s could not be sent", row.id, exc_info=True)
            continue
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        sent += 1
    db.commit()
    return sent
