"""Webhook notifications: signature check, parsing, events."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, Tuple, Union

from unione.api.webhook import WebhookApi, WebhookCallback, WebhookCallbackEventsByUserItem, WebhookCallbackEventsByUserItemEventsItem

from . import signature

__all__ = ["WebhookError", "parse", "events", "WebhookCallback", "WebhookCallbackEventsByUserItem", "WebhookCallbackEventsByUserItemEventsItem"]


class WebhookError(Exception):
    """Rejected notification: status is the HTTP status of the answer (401 signature, 400 body)."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def parse(body: Union[bytes, str], api_key: str) -> Tuple[WebhookCallback, Dict[str, Any]]:
    """Checks the signature and parses the notification: (callback model, decoded body)."""
    if not signature.verify(body, api_key):
        raise WebhookError("Invalid signature", 401)
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    try:
        payload = json.loads(text)
        callback = WebhookApi.parse_callback(text)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        raise WebhookError(f"Invalid body: {e}", 400) from e
    return callback, payload


def events(callback: WebhookCallback) -> Iterator[Tuple[WebhookCallbackEventsByUserItemEventsItem, WebhookCallbackEventsByUserItem]]:
    """Every event of the notification with its user/project."""
    for user in callback.events_by_user or []:
        for event in user.events or []:
            yield event, user
