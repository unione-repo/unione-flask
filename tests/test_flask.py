"""Tests of the Flask extension: client, webhook route and signals, configuration. No network: the HTTP layer
of the SDK is faked (fake_api.py).

    pip install -e ".[test]" && python -m unittest discover -s tests -v
"""
import os
import unittest

from flask import Flask

from fake_api import API_KEY, BASE_PATH, BASE_URL, KEY_HEADER, PLATFORM, WEBHOOK_PATH, FakeApi, clean_env, signed
from unione_wrapper import UniOne, get_client, webhook_event_received, webhook_received
from unione_wrapper.webhook import WebhookCallback


def make_app(**config):
    app = Flask("test")
    app.config.update({"UNIONE_API_KEY": API_KEY, "UNIONE_HOST": BASE_URL, **config})
    return app, UniOne(app)


def has_webhook(app, path=WEBHOOK_PATH):
    return any(rule.rule == path for rule in app.url_map.iter_rules())


class Base(unittest.TestCase):
    def setUp(self):
        clean_env(self)
        self.api = FakeApi(self)


class ClientTest(Base):
    def test_client_from_config(self):
        app, ext = make_app()
        with app.app_context():
            client = get_client()
            self.assertIs(client, ext.client)
            self.assertIs(client, get_client(app))
            client.system.ping()
        call = self.api.only_call()
        self.assertEqual(call.path, BASE_PATH + "/system/ping.json")
        self.assertEqual(call.headers[KEY_HEADER], API_KEY)
        self.assertEqual(call.platform, PLATFORM)

    def test_init_app(self):
        app = Flask("test")
        app.config.update({"UNIONE_API_KEY": API_KEY, "UNIONE_HOST": BASE_URL})
        UniOne().init_app(app)
        self.assertEqual(get_client(app).api_client.config.base_url, BASE_URL)

    def test_environment_and_config(self):
        os.environ["UNIONE_API_KEY"] = "env-key"
        app = Flask("env")
        UniOne(app)
        self.assertEqual(get_client(app).api_client.config.api_key, "env-key")
        app, _ = make_app()
        self.assertEqual(get_client(app).api_client.config.api_key, API_KEY)  # app.config wins

    def test_missing_key(self):
        app, _ = make_app(UNIONE_API_KEY="")
        with self.assertRaises(RuntimeError):
            get_client(app)

    def test_not_initialized(self):
        with self.assertRaises(RuntimeError):
            get_client(Flask("bare"))


class WebhookTest(Base):
    def receive(self, app):
        received = []

        def on_notification(sender, **kwargs):
            received.append(kwargs)

        for signal in (webhook_received, webhook_event_received):
            signal.connect(on_notification, app)
            self.addCleanup(signal.disconnect, on_notification, app)
        return received

    def post(self, app, body, path=WEBHOOK_PATH):
        return app.test_client().post(path, data=body, content_type="application/json")

    def test_get(self):
        app, _ = make_app()
        self.assertEqual(app.test_client().get(WEBHOOK_PATH).status_code, 200)

    def test_signed_post(self):
        app, _ = make_app()
        received = self.receive(app)
        response = self.post(app, signed())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(received), 3)
        self.assertIsInstance(received[0]["callback"], WebhookCallback)
        self.assertEqual(received[1]["event"].event_data.email, "user@example.com")
        self.assertEqual(self.api.calls, [])

    def test_wrong_signature(self):
        app, _ = make_app()
        received = self.receive(app)
        body = signed().replace(b"user@", b"evil@")
        self.assertEqual(self.post(app, body).status_code, 401)
        self.assertEqual(received, [])

    def test_webhook_key_and_path(self):
        app, _ = make_app(UNIONE_WEBHOOK_KEY="hook-key", UNIONE_WEBHOOK_PATH="/hooks/mail")
        self.assertEqual(self.post(app, signed("hook-key"), "/hooks/mail").status_code, 200)
        self.assertEqual(self.post(app, signed(), "/hooks/mail").status_code, 401)
        self.assertFalse(has_webhook(app))

    def test_disabled(self):
        app, _ = make_app(UNIONE_WEBHOOK_ENABLED=False)
        self.assertFalse(has_webhook(app))
        self.assertEqual(self.post(app, signed()).status_code, 404)

    def test_enabled_flag_of_the_environment(self):
        os.environ["UNIONE_WEBHOOK_ENABLED"] = "false"
        off, _ = make_app()
        on, _ = make_app(UNIONE_WEBHOOK_ENABLED=True)  # app.config wins over the environment
        self.assertFalse(has_webhook(off))
        self.assertTrue(has_webhook(on))


if __name__ == "__main__":
    unittest.main()
