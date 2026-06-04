"""Discord webhook notifications."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    success: bool
    detail: str


class DiscordNotifier:
    def __init__(self, webhook_url: str | None, *, timeout_seconds: float = 5.0) -> None:
        self.webhook_url = webhook_url.strip() if webhook_url else None
        self.timeout_seconds = timeout_seconds

    def send(self, *, title: str, message: str) -> NotificationResult:
        if not self.webhook_url:
            return NotificationResult(sent=False, success=True, detail="Discord webhook is not configured")

        payload = {
            "content": None,
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": 0x2F80ED,
                }
            ],
        }

        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return NotificationResult(sent=True, success=False, detail=str(exc))

        return NotificationResult(sent=True, success=True, detail=f"Discord returned HTTP {response.status_code}")
