# WhatsApp

## Meta WhatsApp Cloud API (sem coexistência)

The first concrete connector is `whatsapp_cloud`, backed directly by Meta's
Graph API. It does not use Embedded Signup or WhatsApp Business App
coexistence. The instance endpoint verifies the WABA and the selected phone
number before saving it, and can subscribe the app to the WABA webhook events.

Create an instance with `POST /api/v1/whatsapp/instances/cloud-api`:

```json
{
  "company_id": "company-uuid",
  "name": "Support WhatsApp",
  "credentials": {
    "app_id": "123456789012345",
    "app_secret": "META_APP_SECRET",
    "access_token": "SYSTEM_USER_ACCESS_TOKEN",
    "business_account_id": "102030405060708",
    "phone_number_id": "109876543210987",
    "webhook_verify_token": "token-chosen-by-the-application",
    "api_version": "v25.0"
  },
  "subscribe_to_webhooks": true
}
```

The access token must have the WhatsApp permissions required by the chosen
operations (`whatsapp_business_messaging` for messages and
`whatsapp_business_management` for WABA management). The user must configure
the Meta App Webhooks callback as:

`https://<public-host>/api/v1/whatsapp/webhooks/meta`

The same `webhook_verify_token` must be entered in Meta. The GET challenge is
answered publicly; POST payloads are accepted only when their
`X-Hub-Signature-256` matches the stored App Secret. Inbound messages and
delivery statuses are normalized into the existing contact, conversation and
message tables.

Credentials are never returned in API responses. Protect the database and use
encryption at rest for the JSON credentials column in production.

The module stores a normalized WhatsApp domain and does not depend on a
provider SDK. Each instance identifies the transport with two
application-defined values:

- `integration_type`: `official` or `unofficial`.
- `adapter`: the key of the library adapter registered by the application.

The provider-specific payload is kept in `config` and `metadata`. Credentials
are accepted during integration creation/update but are never returned by the
API; production deployments should protect the database and encrypt sensitive
values at rest.

## HTTP API

All management routes require the existing bearer token and are prefixed with
`/api/v1/whatsapp`. The two `/webhooks/meta` routes are public because Meta
calls them directly; they validate the verification token or App Secret.

| Resource | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| Instances | `POST /instances` | `GET /instances`, `GET /instances/{id}` | `PUT /instances/{id}` | `DELETE /instances/{id}` |
| Meta Cloud API | `POST /instances/cloud-api` | — | `PUT /instances/{id}/cloud-api`, `POST /instances/{id}/verify` | — |
| Contacts | `POST /contacts` | `GET /contacts`, `GET /contacts/{id}` | `PUT /contacts/{id}` | `DELETE /contacts/{id}` |
| Conversations | `POST /conversations` | `GET /conversations`, `GET /conversations/{id}` | `PUT /conversations/{id}` | `DELETE /conversations/{id}` |
| Messages | `POST /messages` | `GET /messages`, `GET /messages/{id}` | `PUT /messages/{id}` | `DELETE /messages/{id}` |

Messages for one conversation can also be read with
`GET /conversations/{conversation_id}/messages`.

The inbox is synchronized through the authenticated SSE endpoint
`GET /instances/events?company_id={company_id}`. It emits instance, contact,
conversation and message changes after the database transaction succeeds.
The browser then reloads the scoped resource with its bearer token; event
frames never contain credentials, access tokens, or raw provider payloads.
The included broker is process-local, which is appropriate for a single API
process. Before running multiple API replicas, replace it with a shared
broker such as Redis Pub/Sub so every replica fans out the same event.

Deletes are soft deletes. `company_id` is required when an instance is
created. For a regular company member, the value must be the member's company;
an owner can select one of their active companies with the optional
`company_id` query parameter when listing resources.

## Registering An Adapter

The application owns the adapter implementation. It can use an unofficial
client, an internal gateway, or any other library:

```python
from app.modules.whatsapp.adapters import (
    AdapterMessageResult,
    whatsapp_adapter_registry,
)
from app.modules.whatsapp.models import IntegrationType


class MyWhatsAppAdapter:
    name = "my-whatsapp-library"
    integration_type = IntegrationType.UNOFFICIAL

    def send_message(self, *, integration, message):
        external_id = "provider-message-id"
        # Call the chosen provider library here.
        return AdapterMessageResult(external_id=external_id, status="sent")


whatsapp_adapter_registry.register(MyWhatsAppAdapter())
```

The value stored in `WhatsAppIntegration.adapter` must match `name`. The
registry is deliberately runtime-only: registering an adapter does not alter
the database schema and the database does not serialize SDK objects.
