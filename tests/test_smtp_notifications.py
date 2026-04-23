from __future__ import annotations

import smtplib

from backend.services import smtp_notifications


def test_effective_smtp_timeout_uses_large_payload_minimum(monkeypatch):
    monkeypatch.setattr(smtp_notifications.settings, "SMTP_TIMEOUT_SECONDS", 10.0)

    timeout = smtp_notifications._effective_smtp_timeout_seconds(
        smtp_notifications.LARGE_EMAIL_THRESHOLD_BYTES
    )

    assert timeout == 60.0


def test_effective_smtp_timeout_respects_higher_configured_value(monkeypatch):
    monkeypatch.setattr(smtp_notifications.settings, "SMTP_TIMEOUT_SECONDS", 90.0)

    timeout = smtp_notifications._effective_smtp_timeout_seconds(1024)

    assert timeout == 90.0


def test_format_smtp_error_reports_underlying_timeout():
    try:
        try:
            raise TimeoutError("The write operation timed out")
        except TimeoutError:
            raise smtplib.SMTPServerDisconnected("Server not connected")
    except smtplib.SMTPServerDisconnected as exc:
        message = smtp_notifications._format_smtp_error(
            exc,
            attached_count=3,
            total_attachment_bytes=12 * 1024 * 1024,
            timeout_seconds=60.0,
        )

    assert "timed out" in message
    assert "3 attachment(s)" in message
    assert "12.0 MB" in message
    assert "60s" in message


def test_format_smtp_error_falls_back_to_original_message():
    message = smtp_notifications._format_smtp_error(
        RuntimeError("smtp down"),
        attached_count=1,
        total_attachment_bytes=0,
        timeout_seconds=60.0,
    )

    assert message == "smtp down"
