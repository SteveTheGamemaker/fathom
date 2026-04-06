"""Notification service — sends webhook alerts on grab and import events."""

from __future__ import annotations

import logging

import httpx

from fathom.config import settings

log = logging.getLogger(__name__)


async def _send_webhook(payload: dict) -> bool:
    """Send a JSON payload to the configured webhook URL."""
    url = settings.notifications.webhook_url
    if not url:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code < 300:
                return True
            log.warning("Webhook returned %d: %s", resp.status_code, resp.text[:200])
            return False
    except Exception:
        log.exception("Webhook notification failed")
        return False


async def notify_grab(release_title: str, quality: str, indexer: str = "") -> None:
    """Send a notification when a release is grabbed."""
    if not settings.notifications.on_grab:
        return

    # Discord-compatible embed format (also works with many webhook receivers)
    payload = {
        "content": None,
        "embeds": [{
            "title": "Release Grabbed",
            "description": release_title,
            "color": 2277115,  # cyan-ish
            "fields": [
                {"name": "Quality", "value": quality, "inline": True},
            ],
        }],
    }
    if indexer:
        payload["embeds"][0]["fields"].append(
            {"name": "Indexer", "value": indexer, "inline": True}
        )

    await _send_webhook(payload)


async def notify_import(title: str, quality: str, file_path: str = "") -> None:
    """Send a notification when a download is imported."""
    if not settings.notifications.on_import:
        return

    payload = {
        "content": None,
        "embeds": [{
            "title": "Download Imported",
            "description": title,
            "color": 5025616,  # green-ish
            "fields": [
                {"name": "Quality", "value": quality, "inline": True},
            ],
        }],
    }
    if file_path:
        payload["embeds"][0]["fields"].append(
            {"name": "Path", "value": file_path, "inline": False}
        )

    await _send_webhook(payload)
