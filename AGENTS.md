# AGENTS.md

UniOne Flask — Flask integration of the UniOne Python SDK (``) for the UniOne transactional email Web API (Web API 1.90). How to integrate UniOne into a Flask application comes first; the last section is about changing this package.

## Integrating UniOne with this package

Flask integration of the [UniOne Python SDK](https://github.com/unione-repo/unione-python-sdk) (``): the API client in the extension (`app.extensions`), a webhook endpoint with signature check. Full guide: [README.md](README.md).

### Install

```bash
pip install unione-flask
```

Requirements: Python 3.8+, Flask 2.3+.

### Configuration

The API key goes to `UNIONE_API_KEY`.

```python
from flask import Flask
from unione_wrapper import UniOne

app = Flask(__name__)
app.config["UNIONE_API_KEY"] = "YOUR_API_KEY"   # default: the environment variable
app.config["UNIONE_HOST"] = "us1.unione.io"
UniOne(app)
```

`us1.unione.io` in the example is for an account on another datacenter; without the host setting the package uses `api.unione.io`.

| Option | Environment variable | Default | Description |
|---|---|---|---|
| `UNIONE_API_KEY` | `UNIONE_API_KEY` |  | User or project API key (required). |
| `UNIONE_HOST` | `UNIONE_HOST` | `api.unione.io` | API host (datacenter: `api.unione.io`, `eu1.unione.io`, `us1.unione.io`) or a full base URL. |
| `UNIONE_TIMEOUT` | `UNIONE_TIMEOUT` | `30` | Request timeout, seconds. |
| `UNIONE_WEBHOOK_KEY` | `UNIONE_WEBHOOK_KEY` |  | API key the webhooks are signed with (the key of the user/project of the webhook), if it differs from the API key. |
| `UNIONE_WEBHOOK_PATH` | `UNIONE_WEBHOOK_PATH` | `/unione/webhook` | Path of the webhook endpoint. |

### API client

The client calls [email/send](https://docs.unione.io/en/web-api-ref#email-send) with all of its options: templates, substitutions, metadata, tracking. Fields of the request and other examples: [Python SDK docs](https://github.com/unione-repo/unione-python-sdk/blob/HEAD/docs/Email.md#send).

```python
from unione.api.email import EmailSendRequest, MessageObject, MessageObjectRecipientsItem as Recipient
from unione.common import BodyObject
from unione_wrapper import get_client


@app.post("/send")
def send_email():
    client = get_client()
    response = client.email.send(EmailSendRequest(
        message=MessageObject(
            recipients=[Recipient.from_address("Alex <alex@example.com>")],
            from_email="shop@example.com",
            from_name="Shop",
            subject="Your order",
            body=BodyObject.from_html("<p>Hello, {{to_name}}! Your order has shipped.</p>"),
        ),
    ))
    return {"job_id": response.job_id}
```

### Webhooks

The endpoint answers `GET` with 200 OK (the URL check of [webhook/set](https://docs.unione.io/en/web-api-ref#webhook-set)) and accepts the `POST` notifications: it checks the `auth` field (MD5 of the request body in which the `auth` value is replaced by the API key), answers 401 to a wrong signature, and passes the notification and each of its events to the application.

```python
from unione_wrapper import webhook_event_received


@webhook_event_received.connect_via(app)
def on_event(sender, event, user, **kwargs):
    data = event.event_data
    app.logger.info("%s %s %s", event.event_name, data.email, data.status)
```

Register the URL of the endpoint with `webhook/set`, e.g. `https://example.com/unione/webhook`.

> **Answer 200 within 3 seconds** and process the events in the background (a queue): otherwise UniOne repeats the request every 10 minutes for 24 hours (`retry_count` grows), and a handler that failed every request for at least 10 events of a day is turned inactive. The handler must take at least **5 parallel requests of up to 100 events each**; deduplicate, a repeat delivers the same events again.

### Rules for generated code

- Server-side only. Read the API key from `UNIONE_API_KEY`; never put it in browser or mobile code, never commit it.
- Base URL `https://api.unione.io/en/transactional/api/v1` (an account registered on another host uses that one: `eu1.unione.io`, `us1.unione.io`); every method is POST with a JSON body; auth header `X-API-KEY`. The package does all of it.
- First email without DNS: `domain/get-sandbox-domain` → `confirmed-email/create` (the user clicks the link within 48 hours) → `email/send` from `noreply@<sandbox-domain>` to the confirmed address. Account API key only; up to 10 confirmed addresses, 100 emails a day. The domain is deleted 31 days after it was created: the next `domain/get-sandbox-domain` call creates a new one with another name, so read the name from the response, never hardcode it.
- Never ship a sandbox domain as the production sender (it is not in `domain/list`); read `from_email` from config. Production needs a verified domain: `domain/get-dns-records` → DNS records (verification TXT as is, DKIM TXT `v=DKIM1; k=rsa; p=<dkim>` on `<selector>._domainkey`, CNAME `_dmarc` → the `dmarc` field; SPF `include:spf.unione.io` is not in the response) → `domain/validate-verification-record`, `domain/validate-dkim` → `domain/list`.
- Set `message.idempotence_key` on retryable sends; retry network errors, `429` and `5xx` with backoff, not other errors unchanged. Up to 500 recipients and 10 MB per request with the attachments in base64 (a third larger than the files); always `body.html` or `body.plaintext`.
- Delivery events via webhook (`webhook/set`), not polling; the webhook endpoint of this package checks the `auth` signature (401 when wrong). Keep the listeners fast: answer 200 within 3 seconds and process the events from a queue, otherwise the request is repeated every 10 minutes for 24 hours; take at least 5 parallel requests of up to 100 events each; deduplicate.
- Keep the default unsubscribe and tracking behaviour; changes go through UniOne support.
- Do not invent methods or fields. Check the [README](README.md), the [API reference](https://docs.unione.io/en/web-api-ref) or [llms.txt](https://docs.unione.io/llms.txt).

### Reference

- [UniOne Python SDK](https://github.com/unione-repo/unione-python-sdk): every API method, models, errors ([AGENTS.md](https://github.com/unione-repo/unione-python-sdk/blob/HEAD/AGENTS.md))
- [API reference](https://docs.unione.io/en/web-api-ref)
- [Full API reference for LLMs](https://docs.unione.io/llms-full.txt)

## Working on this repository

- **Generated code.** The whole package is generated by the UniOne team from the UniOne Web API OpenAPI spec (Web API 1.90): sources, docs, README.md and this file. Do not hand-edit it: the next release replaces the content of this repository. Report problems and requests in the issues of this repository (https://github.com/unione-repo/unione-flask).
- **Build and check:**

  ```bash
  python -m pip install -e .
  ```

- **Source label.** Every request carries the query parameter `platform=flask.1.2.4,python-sdk.1.2.4` (this package, then the SDK it is built on).
- **Tests.** Before a release the generator installs the package into a test app of Flask and checks the client, the webhook endpoint against a mock of the API: no real API key, no real sends.
- **Release.** The version (1.2.4 in pyproject.toml) and the tag `v1.2.4` come from the generator; README.md states the Web API version the release was generated from.
- **Secrets.** Never commit API keys; the examples read `UNIONE_API_KEY` from the environment.
