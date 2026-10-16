"""Settings of the UniOne API: environment variables UNIONE_* with overrides of the framework config."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

ENV_PREFIX = "UNIONE_"
DEFAULT_WEBHOOK_PATH = "/unione/webhook"


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    """User or project API key."""

    host: Optional[str] = None
    """API host (datacenter: api.unione.io, eu1.unione.io, us1.unione.io) or a full base URL; None: the default one."""

    timeout: float = 30.0
    """Request timeout, seconds."""

    webhook_key: Optional[str] = None
    """API key the webhooks are signed with; None: api_key."""

    webhook_path: str = DEFAULT_WEBHOOK_PATH
    """Path of the webhook endpoint."""

    @property
    def signing_key(self) -> str:
        return self.webhook_key or self.api_key

    @classmethod
    def load(cls, overrides: Optional[Mapping[str, Any]] = None, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        """Environment variables UNIONE_API_KEY, ..._HOST, ..._TIMEOUT, ..._WEBHOOK_KEY, ..._WEBHOOK_PATH; overrides
        (keys api_key, host, ... in any case) win over them."""
        env = os.environ if environ is None else environ
        values = {key: env.get(ENV_PREFIX + key.upper()) for key in ("api_key", "host", "timeout", "webhook_key", "webhook_path")}
        for key, value in (overrides or {}).items():
            if key.lower() in values and value is not None:
                values[key.lower()] = value
        return cls(
            api_key=str(values["api_key"] or ""),
            host=str(values["host"]) if values["host"] else None,
            timeout=float(values["timeout"] or 30.0),
            webhook_key=str(values["webhook_key"]) if values["webhook_key"] else None,
            webhook_path=str(values["webhook_path"] or DEFAULT_WEBHOOK_PATH),
        )

    def require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("UniOne: the API key is not set (UNIONE_API_KEY).")
        return self.api_key
