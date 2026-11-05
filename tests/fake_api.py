"""Test helpers: the fake HTTP layer of the SDK, the sample webhook notification, a clean environment."""
import json
import os
import sys
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from unione.client import UrllibTransport  # noqa: E402
from unione.client.api_client import PLATFORM as SDK_PLATFORM  # noqa: E402

from unione_wrapper._settings import ENV_PREFIX  # noqa: E402
from unione_wrapper.signature import sign  # noqa: E402

API_KEY = "test-key"
BASE_URL = "http://127.0.0.1:9/api/v1"
"""Explicit API host of the tests (a closed local port): nothing may reach the real API."""
BASE_PATH = "/api/v1"
KEY_HEADER = "X-API-KEY"
SEND_PATH = "/email/send.json"
PLATFORM = "flask.1.3.0," + SDK_PLATFORM
"""The "platform" query parameter of the requests of the wrapper."""
WEBHOOK_PATH = "/unione/webhook"
SAMPLE = json.dumps({
    "auth": "00000000000000000000000000000000",
    "events_by_user": [
        {
            "user_id": 1,
            "project_id": "6432890213745872",
            "events": [
                {
                    "event_name": "transactional_email_status",
                    "event_data": {
                        "job_id": "1a3Q2V-0000OZ-S0",
                        "email": "user@example.com",
                        "status": "delivered",
                        "event_time": "2015-11-30 15:09:42",
                    },
                },
                {
                    "event_name": "transactional_spam_block",
                    "event_data": {
                        "block_time": "2015-11-30 15:09:42",
                        "block_type": "one_smtp",
                        "domain": "example.com",
                        "SMTP_blocks_count": 1,
                        "domain_status": "blocked",
                    },
                },
            ],
        },
    ],
})
"""A notification with two events, "auth" is the placeholder of signature.sign()."""
SEND_RESPONSE = {"status": "success", "job_id": "1ZymBc-00041N-9X", "emails": ["user@example.com"],
                 "failed_emails": {}}
API_ERROR = {"status": "error", "message": "Unknown recipient", "code": 204}


def signed(key=API_KEY):
    return sign(SAMPLE, key)


class Call:
    """A request the SDK sent: path, platform, headers, decoded JSON body."""

    def __init__(self, method, url, headers, body):
        parts = urllib.parse.urlsplit(url)
        self.method, self.url, self.path = method, url, parts.path
        self.platform = (urllib.parse.parse_qs(parts.query).get("platform") or [""])[0]
        self.headers = dict(headers)
        self.body = json.loads(body.decode("utf-8")) if body else None


class FakeApi:
    """Replaces the HTTP layer of the SDK for a test: every request is recorded and answered by reply()."""

    def __init__(self, test):
        self.calls = []
        self.replies = {}
        patcher = mock.patch.object(UrllibTransport, "send", self._send)
        patcher.start()
        test.addCleanup(patcher.stop)

    def reply(self, path, status, data):
        """Answer of the requests to an API path ("/email/send.json"): HTTP status and JSON."""
        self.replies[path] = (status, json.dumps(data).encode("utf-8"))

    def only_call(self):
        assert len(self.calls) == 1, "expected one request, got %d" % len(self.calls)
        return self.calls[0]

    def _send(self, method, url, headers, body, timeout):
        call = Call(method, url, headers, body)
        self.calls.append(call)
        path = call.path[len(BASE_PATH):] if call.path.startswith(BASE_PATH) else call.path
        if path in self.replies:
            return self.replies[path]
        data = SEND_RESPONSE if path == SEND_PATH else {"status": "success", "user_id": 1}
        return 200, json.dumps(data).encode("utf-8")


def clean_env(test):
    """No UNIONE_* variables of the machine (the tests set their own) and no proxies for the test client."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(ENV_PREFIX)}
    env.update(NO_PROXY="*", no_proxy="*")
    patcher = mock.patch.dict(os.environ, env, clear=True)
    patcher.start()
    test.addCleanup(patcher.stop)
