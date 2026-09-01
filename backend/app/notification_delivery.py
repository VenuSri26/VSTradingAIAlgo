"""Safe notification outbox with optional webhook and SMTP email delivery.

Notifications are persisted before delivery. All delivery channels are disabled
by default and never influence trading decisions or enable broker execution.
"""
from __future__ import annotations

import json
import smtplib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from threading import RLock
from typing import Any
from urllib import request


@dataclass
class DeliveryState:
    queued: int = 0
    delivered: int = 0
    failed: int = 0
    last_delivery_at: str | None = None
    last_error: str | None = None


class NotificationDelivery:
    def __init__(
        self,
        outbox_path: str,
        webhook_url: str | None = None,
        timeout_sec: float = 5.0,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        smtp_from: str | None = None,
        smtp_to: str | None = None,
        smtp_to_info: str | None = None,
        smtp_to_warning: str | None = None,
        smtp_to_critical: str | None = None,
        smtp_to_broker: str | None = None,
        smtp_to_infrastructure: str | None = None,
        smtp_to_trading: str | None = None,
        whatsapp_enabled: bool = False,
        whatsapp_api_url: str | None = None,
        whatsapp_token: str | None = None,
        whatsapp_to: str | None = None,
        smtp_use_tls: bool = True,
        retry_base_sec: float = 60.0,
        retry_max_sec: float = 3600.0,
        max_attempts: int = 8,
    ):
        self.path = Path(outbox_path)
        self.webhook_url = (webhook_url or "").strip() or None
        self.timeout_sec = max(1.0, float(timeout_sec))
        self.smtp_host = (smtp_host or "").strip() or None
        self.smtp_port = int(smtp_port)
        self.smtp_username = (smtp_username or "").strip() or None
        self.smtp_password = smtp_password or None
        self.smtp_from = (smtp_from or "").strip() or self.smtp_username
        self.smtp_to = [x.strip() for x in (smtp_to or "").split(",") if x.strip()]
        self.smtp_to_by_severity = {
            "INFO": [x.strip() for x in (smtp_to_info or "").split(",") if x.strip()],
            "WARNING": [x.strip() for x in (smtp_to_warning or "").split(",") if x.strip()],
            "CRITICAL": [x.strip() for x in (smtp_to_critical or "").split(",") if x.strip()],
        }
        self.smtp_to_by_category = {
            "BROKER": [x.strip() for x in (smtp_to_broker or "").split(",") if x.strip()],
            "INFRASTRUCTURE": [x.strip() for x in (smtp_to_infrastructure or "").split(",") if x.strip()],
            "TRADING": [x.strip() for x in (smtp_to_trading or "").split(",") if x.strip()],
        }
        self.whatsapp_enabled_flag = bool(whatsapp_enabled)
        self.whatsapp_api_url = (whatsapp_api_url or "").strip() or None
        self.whatsapp_token = (whatsapp_token or "").strip() or None
        self.whatsapp_to = (whatsapp_to or "").strip() or None
        self.smtp_use_tls = bool(smtp_use_tls)
        self.retry_base_sec = max(10.0, float(retry_base_sec))
        self.retry_max_sec = max(self.retry_base_sec, float(retry_max_sec))
        self.max_attempts = max(1, int(max_attempts))
        self._lock = RLock()
        self._state = DeliveryState()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_url)

    @property
    def email_enabled(self) -> bool:
        recipients = self.smtp_to or [x for values in self.smtp_to_by_severity.values() for x in values]
        return bool(self.smtp_host and self.smtp_from and recipients)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_enabled_flag and self.whatsapp_api_url and self.whatsapp_token and self.whatsapp_to)

    @property
    def delivery_enabled(self) -> bool:
        return self.webhook_enabled or self.email_enabled or self.whatsapp_enabled

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
        self.path.write_text(text, encoding="utf-8")

    def enqueue(self, code: str, severity: str, message: str, action: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = self._read()
        for row in reversed(rows):
            if row.get("status") == "PENDING" and row.get("code") == code and row.get("message") == message:
                return row
        item = {
            "id": f"{int(datetime.now(timezone.utc).timestamp()*1000)}-{len(rows)+1}",
            "created_at": self._now(), "code": code, "severity": severity,
            "message": message, "action": action, "metadata": metadata or {},
            "status": "PENDING", "attempts": 0, "delivered_at": None,
            "next_attempt_at": self._now(), "acknowledged_at": None,
            "escalation_level": 0, "escalated_at": None,
            "delivered_channels": [], "channel_errors": {}, "last_error": None,
            "live_orders_enabled": False,
        }
        rows.append(item)
        self._write(rows)
        with self._lock:
            self._state.queued += 1
        return item

    def _send_webhook(self, row: dict[str, Any]) -> None:
        payload = json.dumps({k: row[k] for k in ("code", "severity", "message", "action", "metadata")}).encode()
        req = request.Request(self.webhook_url, data=payload, method="POST", headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=self.timeout_sec) as response:  # noqa: S310 - admin configured endpoint
            if not 200 <= int(response.status) < 300:
                raise RuntimeError(f"webhook returned HTTP {response.status}")

    def _send_email(self, row: dict[str, Any]) -> None:
        message = EmailMessage()
        message["Subject"] = f"[{row.get('severity', 'INFO')}] VSTradingAI: {row.get('code')}"
        message["From"] = self.smtp_from
        severity = str(row.get("severity") or "INFO").upper()
        metadata = row.get("metadata") or {}
        raw_categories = metadata.get("categories") or [metadata.get("category")]
        categories = [str(x).upper() for x in raw_categories if x]
        category_recipients = []
        for category in categories:
            category_recipients.extend(self.smtp_to_by_category.get(category, []))
        recipients = list(dict.fromkeys(category_recipients)) or self.smtp_to_by_severity.get(severity) or self.smtp_to
        if not recipients:
            raise RuntimeError(f"no SMTP recipients configured for severity {severity}")
        message["To"] = ", ".join(recipients)
        message.set_content(
            f"{row.get('message')}\n\nRecommended action: {row.get('action')}\n"
            f"Created: {row.get('created_at')}\nMetadata: {json.dumps(row.get('metadata') or {}, indent=2)}\n"
            "\nSafety: live broker orders remain disabled."
        )
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout_sec) as client:
            if self.smtp_use_tls:
                client.starttls()
            if self.smtp_username:
                client.login(self.smtp_username, self.smtp_password or "")
            client.send_message(message)


    def _send_whatsapp(self, row: dict[str, Any]) -> None:
        payload = {
            "to": self.whatsapp_to,
            "type": "text",
            "text": {
                "body": (
                    f"[{row.get('severity', 'INFO')}] VSTradingAI {row.get('code')}\n"
                    f"{row.get('message')}\nAction: {row.get('action')}\n"
                    "Safety: live broker orders remain disabled."
                )[:4000]
            },
        }
        req = request.Request(
            self.whatsapp_api_url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.whatsapp_token}",
            },
        )
        with request.urlopen(req, timeout=self.timeout_sec) as response:  # noqa: S310 - admin configured endpoint
            if not 200 <= int(response.status) < 300:
                raise RuntimeError(f"WhatsApp endpoint returned HTTP {response.status}")

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    def acknowledge(self, item_id: str, note: str = "") -> dict[str, Any]:
        rows = self._read()
        for row in rows:
            if str(row.get("id")) == str(item_id):
                row["status"] = "ACKNOWLEDGED"
                row["acknowledged_at"] = self._now()
                row["acknowledgement_note"] = str(note)[:300]
                self._write(rows)
                return row
        raise KeyError(item_id)

    def escalate_pending(self, after_sec: float = 900.0) -> dict[str, Any]:
        rows = self._read()
        now = datetime.now(timezone.utc)
        escalated = 0
        for row in rows:
            if row.get("status") != "PENDING" or str(row.get("severity", "")).upper() != "CRITICAL":
                continue
            created = self._parse_time(row.get("created_at"))
            if not created or (now-created).total_seconds() < max(60.0, float(after_sec)):
                continue
            if int(row.get("escalation_level") or 0) >= 1:
                continue
            row["escalation_level"] = 1
            row["escalated_at"] = self._now()
            row["action"] = f"ESCALATED: {row.get('action') or 'REVIEW IMMEDIATELY'}"[:120]
            row["next_attempt_at"] = self._now()
            escalated += 1
        if escalated:
            self._write(rows)
        return {"escalated": escalated, "live_orders_enabled": False}

    def dispatch(self, limit: int = 20) -> dict[str, Any]:
        rows = self._read()
        processed = delivered = failed = 0
        channel_counts = {"webhook": 0, "email": 0, "whatsapp": 0}
        for row in rows:
            if processed >= max(1, min(int(limit), 100)):
                break
            if row.get("status") != "PENDING":
                continue
            attempts = int(row.get("attempts") or 0)
            if attempts >= self.max_attempts:
                row["status"] = "FAILED"
                row["last_error"] = "MAX_ATTEMPTS_REACHED"
                failed += 1
                continue
            next_attempt = self._parse_time(row.get("next_attempt_at"))
            if next_attempt and next_attempt > datetime.now(timezone.utc):
                continue
            processed += 1
            row["attempts"] = attempts + 1
            if not self.delivery_enabled:
                row["last_error"] = "DELIVERY_DISABLED"
                delay = min(self.retry_max_sec, self.retry_base_sec * (2 ** max(0, row["attempts"]-1)))
                row["next_attempt_at"] = (datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
                continue
            errors: dict[str, str] = {}
            delivered_channels: list[str] = []
            for channel, enabled, sender in (
                ("webhook", self.webhook_enabled, self._send_webhook),
                ("email", self.email_enabled, self._send_email),
                ("whatsapp", self.whatsapp_enabled, self._send_whatsapp),
            ):
                if not enabled:
                    continue
                try:
                    sender(row)
                    delivered_channels.append(channel)
                    channel_counts[channel] += 1
                except Exception as exc:
                    errors[channel] = str(exc)[:300]
            row["delivered_channels"] = delivered_channels
            row["channel_errors"] = errors
            if delivered_channels:
                row["status"] = "DELIVERED" if not errors else "PARTIAL"
                row["delivered_at"] = self._now()
                row["last_error"] = "; ".join(f"{k}: {v}" for k, v in errors.items()) or None
                row["next_attempt_at"] = None
                delivered += 1
            else:
                row["last_error"] = "; ".join(f"{k}: {v}" for k, v in errors.items()) or "DELIVERY_FAILED"
                delay = min(self.retry_max_sec, self.retry_base_sec * (2 ** max(0, row["attempts"]-1)))
                row["next_attempt_at"] = (datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
                failed += 1
        self._write(rows)
        with self._lock:
            self._state.delivered += delivered
            self._state.failed += failed
            if delivered:
                self._state.last_delivery_at = self._now()
            self._state.last_error = next((r.get("last_error") for r in reversed(rows) if r.get("last_error") not in (None, "DELIVERY_DISABLED")), None)
        return {
            "processed": processed, "delivered": delivered, "failed": failed,
            "channels": channel_counts,
            "delivery_enabled": self.delivery_enabled,
            "webhook_enabled": self.webhook_enabled,
            "email_enabled": self.email_enabled,
            "live_orders_enabled": False,
        }

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._read()[-max(1, min(int(limit), 500)):]))

    def status(self) -> dict[str, Any]:
        rows = self._read()
        pending = sum(1 for r in rows if r.get("status") == "PENDING")
        with self._lock:
            payload = asdict(self._state)
        payload.update({
            "pending": pending, "total": len(rows),
            "delivery_enabled": self.delivery_enabled,
            "webhook_enabled": self.webhook_enabled,
            "email_enabled": self.email_enabled,
            "whatsapp_enabled": self.whatsapp_enabled,
            "email_recipients": len(set(self.smtp_to + [x for values in self.smtp_to_by_severity.values() for x in values] + [x for values in self.smtp_to_by_category.values() for x in values])),
            "severity_routing": {k: len(v) for k, v in self.smtp_to_by_severity.items()},
            "category_routing": {k: len(v) for k, v in self.smtp_to_by_category.items()},
            "outbox_path": str(self.path), "live_orders_enabled": False,
        })
        return payload
