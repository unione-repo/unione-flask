"""UniOne Web API for Flask: API client, webhooks.

    app = Flask(__name__)
    UniOne(app)                      # or ext = UniOne(); ext.init_app(app)
    get_client().system.ping()

Config keys (default: the environment variables of the same names): UNIONE_API_KEY, UNIONE_HOST, UNIONE_TIMEOUT,
UNIONE_WEBHOOK_KEY, UNIONE_WEBHOOK_PATH, UNIONE_WEBHOOK_ENABLED (register the webhook route, default True).
"""
from __future__ import annotations

from typing import Optional

from blinker import Namespace
from flask import Flask, Response, current_app, request
from unione import UniOneClient

from . import webhook as notifications
from ._settings import Settings

__all__ = ["UniOne", "get_client", "webhook_received", "webhook_event_received", "Settings"]
__version__ = "1.2.4"

_signals = Namespace()
webhook_received = _signals.signal("unione-webhook-received")
"""A notification with a valid signature: sender = app, callback (model), payload (decoded body)."""
webhook_event_received = _signals.signal("unione-webhook-event-received")
"""One event of a notification: sender = app, event (event_name, event_data), user (its user/project)."""

_EXTENSION = "unione"
_KEYS = ("API_KEY", "HOST", "TIMEOUT", "WEBHOOK_KEY", "WEBHOOK_PATH")


class _State:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Optional[UniOneClient] = None

    @property
    def client(self) -> UniOneClient:
        if self._client is None:
            s = self.settings
            self._client = UniOneClient(s.require_key(), s.host, s.timeout, platform="flask.1.2.4")
        return self._client


class UniOne:
    """Flask extension of the UniOne API."""

    def __init__(self, app: Optional[Flask] = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        settings = Settings.load({key: app.config.get("UNIONE_" + key) for key in _KEYS})
        app.extensions[_EXTENSION] = _State(settings)
        if app.config.get("UNIONE_WEBHOOK_ENABLED", True):
            app.add_url_rule(settings.webhook_path, endpoint="unione_webhook", view_func=_webhook,
                             methods=["GET", "HEAD", "POST"])

    @property
    def client(self) -> UniOneClient:
        """The client of the current app."""
        return get_client()


def _state(app: Optional[Flask] = None) -> _State:
    app = app or current_app
    try:
        return app.extensions[_EXTENSION]
    except KeyError:
        raise RuntimeError("UniOne is not initialized: call UniOne(app) or init_app(app).") from None


def get_client(app: Optional[Flask] = None) -> UniOneClient:
    """The UniOne API client of the app (default: current_app), one instance per app."""
    return _state(app).client


def _webhook() -> Response:
    """GET/HEAD -> 200 (URL check of webhook/set), POST -> signature check and signals."""
    if request.method != "POST":
        return Response("OK", mimetype="text/plain")
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    try:
        callback, payload = notifications.parse(request.get_data(), _state(app).settings.signing_key)
    except notifications.WebhookError as e:
        return Response(str(e), status=e.status, mimetype="text/plain")
    webhook_received.send(app, callback=callback, payload=payload)
    for event, user in notifications.events(callback):
        webhook_event_received.send(app, event=event, user=user)
    return Response("OK", mimetype="text/plain")
