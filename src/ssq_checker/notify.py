"""Deliver a report to Telegram via the Bot API (stdlib only, no deps)."""
from __future__ import annotations

import json
import urllib.request

API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
DEFAULT_TIMEOUT = 10


def send_telegram(
    text: str,
    token: str,
    chat_id: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """Send `text` to a Telegram chat. Raises on HTTP/transport error."""
    if not token or not chat_id:
        raise ValueError("Telegram token and chat_id are required")
    url = API_TEMPLATE.format(token=token)
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
    result = json.loads(body)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")
