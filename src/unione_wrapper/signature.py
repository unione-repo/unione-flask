"""Signature of the webhook notifications: the "auth" field is the MD5 of the request body in which the "auth"
value is replaced by the API key of the user/project of the webhook."""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Union

_AUTH = re.compile(rb'"auth"\s*:\s*"([0-9a-fA-F]{32})"')
PLACEHOLDER = "0" * 32


def _bytes(value: Union[bytes, str]) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


def verify(body: Union[bytes, str], api_key: str) -> bool:
    """True when the "auth" field of the body is its signature made with api_key."""
    body = _bytes(body)
    match = _AUTH.search(body)
    if not api_key or match is None:
        return False
    auth = match.group(1)
    expected = hashlib.md5(body.replace(auth, _bytes(api_key))).hexdigest()
    return hmac.compare_digest(expected, auth.decode("ascii").lower())


def sign(body: Union[bytes, str], api_key: str, placeholder: str = PLACEHOLDER) -> bytes:
    """Signs a body whose "auth" is the placeholder (32 hex digits), e.g. for tests."""
    body = _bytes(body)
    auth = hashlib.md5(body.replace(_bytes(placeholder), _bytes(api_key))).hexdigest()
    return body.replace(_bytes(placeholder), auth.encode("ascii"))
