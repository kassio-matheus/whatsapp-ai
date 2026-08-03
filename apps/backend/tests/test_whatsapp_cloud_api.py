import hashlib
import hmac
import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.modules.auth.models import User
from app.modules.companies.models import Company
from app.modules.whatsapp import service
from app.modules.whatsapp.cloud_api import (
    CloudApiConnectionInfo,
    MetaCloudApiClient,
    verify_webhook_signature,
)
from app.modules.whatsapp.models import (
    IntegrationType,
    MessageDirection,
    MessageStatus,
    WhatsAppCloudApiCreate,
    WhatsAppCloudApiCredentials,
    WhatsAppContactCreate,
    WhatsAppConversation,
    WhatsAppIntegration,
    WhatsAppMessage,
)
from app.modules.whatsapp.phone_numbers import format_phone_number_for_meta


@pytest.fixture()
def database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _company(session: Session) -> tuple[User, Company]:
    user = User(
        email="cloud-owner@example.com",
        hashed_password="test-password",
        is_super_admin=True,
        is_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    company = Company(name="Cloud Company", owner_id=user.id)
    session.add(company)
    session.commit()
    session.refresh(company)
    return user, company


def _credentials() -> WhatsAppCloudApiCredentials:
    return WhatsAppCloudApiCredentials(
        app_id="123456789012345",
        app_secret="app-secret",
        access_token="system-user-token",
        business_account_id="102030405060708",
        phone_number_id="109876543210987",
        webhook_verify_token="webhook-token",
    )


def test_cloud_api_client_uses_meta_graph_endpoints(monkeypatch) -> None:
    requests: list[tuple[str, str, bytes | None]] = []

    class FakeResponse:
        status = 200

        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        del timeout
        requests.append((request.method, request.full_url, request.data))
        if "/102030405060708?fields=id%2Cname" in request.full_url:
            return FakeResponse({"id": "102030405060708", "name": "Cloud WABA"})
        if "phone_numbers" in request.full_url:
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "109876543210987",
                            "display_phone_number": "+55 11 99999-9999",
                            "verified_name": "Cloud Company",
                            "quality_rating": "GREEN",
                        }
                    ]
                }
            )
        if "message_templates" in request.full_url:
            if request.method == "POST":
                return FakeResponse(
                    {"id": "template-2", "status": "PENDING", "category": "UTILITY"}
                )
            if request.method == "DELETE":
                return FakeResponse({"success": True})
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "template-1",
                            "name": "appointment_reminder",
                            "language": "pt_BR",
                            "status": "APPROVED",
                            "category": "UTILITY",
                            "components": [{"type": "BODY", "text": "Olá {{1}}"}],
                        }
                    ],
                    "paging": {"cursors": {"after": "next-page"}},
                }
            )
        if "/messages" in request.full_url:
            return FakeResponse({"messages": [{"id": "wamid.outbound-1"}]})
        return FakeResponse({"success": True})

    monkeypatch.setattr("app.modules.whatsapp.cloud_api.urlopen", fake_urlopen)
    client = MetaCloudApiClient(_credentials())

    connection = client.verify_connection()
    subscribed = client.subscribe_to_business_account()

    assert connection.business_account_name == "Cloud WABA"
    assert connection.display_phone_number == "+55 11 99999-9999"
    assert subscribed is True
    assert requests[0][0] == "GET"
    assert "/v25.0/102030405060708" in requests[0][1]
    assert requests[1][0] == "GET"
    assert requests[2][0] == "POST"
    assert requests[2][1].endswith("/102030405060708/subscribed_apps")

    templates = client.get_message_templates(limit=25)
    assert templates.next_cursor == "next-page"
    assert templates.data[0].name == "appointment_reminder"
    assert "message_templates" in requests[3][1]
    assert "limit=25" in requests[3][1]

    created_template = client.create_message_template(
        {
            "name": "appointment_reminder",
            "language": "pt_BR",
            "category": "UTILITY",
            "components": [{"type": "BODY", "text": "Olá {{1}}"}],
        }
    )
    assert created_template["id"] == "template-2"
    assert requests[4][0] == "POST"

    result = client.send_message(
        to="+55 75 997136619",
        message=WhatsAppMessage(
            company_id=uuid.uuid4(),
            integration_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            direction=MessageDirection.OUTBOUND.value,
            content="Hello from Cloud API",
        ),
    )
    assert result.external_id == "wamid.outbound-1"
    assert requests[5][0] == "POST"
    assert requests[5][1].endswith("/109876543210987/messages")
    assert json.loads(requests[5][2] or b"{}")["to"] == "557597136619"

    client.send_message(
        to="5511999999999",
        message=WhatsAppMessage(
            company_id=uuid.uuid4(),
            integration_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            direction=MessageDirection.OUTBOUND.value,
            message_type="image",
            content="A useful image",
            media_url="https://cdn.example.com/image.jpg",
        ),
    )
    image_payload = json.loads(requests[6][2] or b"{}")
    assert image_payload["type"] == "image"
    assert image_payload["image"] == {
        "link": "https://cdn.example.com/image.jpg",
        "caption": "A useful image",
    }

    client.send_message(
        to="5511999999999",
        message=WhatsAppMessage(
            company_id=uuid.uuid4(),
            integration_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            direction=MessageDirection.OUTBOUND.value,
            message_type="interactive",
            metadata_json={
                "interactive": {
                    "type": "button",
                    "body": {"text": "Choose one"},
                    "action": {"buttons": []},
                }
            },
        ),
    )
    interactive_payload = json.loads(requests[7][2] or b"{}")
    assert interactive_payload["interactive"]["type"] == "button"

    client.send_message(
        to="5511999999999",
        message=WhatsAppMessage(
            company_id=uuid.uuid4(),
            integration_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            direction=MessageDirection.OUTBOUND.value,
            message_type="template",
            metadata_json={
                "template": {
                    "name": "appointment_reminder",
                    "language": {"code": "pt_BR"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": "Kassio"}],
                        }
                    ],
                }
            },
        ),
    )
    template_payload = json.loads(requests[8][2] or b"{}")
    assert template_payload["type"] == "template"
    assert template_payload["template"]["language"]["code"] == "pt_BR"

    deleted = client.delete_message_template(
        name="appointment_reminder", hsm_id="template-1"
    )
    assert deleted is True
    assert requests[9][0] == "DELETE"
    assert "name=appointment_reminder" in requests[9][1]
    assert "hsm_id=template-1" in requests[9][1]


def test_cloud_api_connection_is_verified_before_storage(monkeypatch, database) -> None:
    connection = CloudApiConnectionInfo(
        app_id="123456789012345",
        business_account_id="102030405060708",
        business_account_name="Cloud WABA",
        phone_number_id="109876543210987",
        display_phone_number="+55 11 99999-9999",
        verified_name="Cloud Company",
        quality_rating="GREEN",
    )

    class FakeMetaClient:
        def __init__(self, credentials) -> None:
            self.credentials = credentials

        def verify_connection(self):
            return connection

        def subscribe_to_business_account(self):
            return True

    monkeypatch.setattr(service, "MetaCloudApiClient", FakeMetaClient)

    with Session(database) as session:
        user, company = _company(session)
        integration, returned_connection, subscribed = (
            service.create_cloud_api_integration(
                session=session,
                current_user=user,
                data=WhatsAppCloudApiCreate(
                    company_id=company.id,
                    name="Meta Cloud",
                    credentials=_credentials(),
                ),
            )
        )

        assert returned_connection == connection
        assert subscribed is True
        assert integration.adapter == "whatsapp_cloud"
        assert integration.external_account_id == "102030405060708"
        assert integration.phone_number == "+55 11 99999-9999"
        assert integration.credentials_json["access_token"] == "system-user-token"
        assert integration.config_json["coexistence"] is False


def test_meta_contact_is_stored_in_meta_phone_format(database) -> None:
    with Session(database) as session:
        user, company = _company(session)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="Meta Cloud",
            integration_type=IntegrationType.OFFICIAL.value,
            adapter="whatsapp_cloud",
            credentials_json=_credentials().model_dump(),
            config_json={"coexistence": False},
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        contact = service.create_contact(
            session=session,
            current_user=user,
            data=WhatsAppContactCreate(
                instance_id=integration.id,
                phone_number="+55 75 997136619",
                name="Jane Doe",
            ),
        )

        assert contact.phone_number == "557597136619"


def test_meta_webhook_signature_and_normalization(database) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "102030405060708",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210987"},
                            "contacts": [
                                {
                                    "profile": {"name": "Jane Doe"},
                                    "wa_id": "5511999999999",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.inbound-1",
                                    "timestamp": "1760000000",
                                    "text": {"body": "Olá"},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode()
    signature = (
        "sha256=" + hmac.new(b"app-secret", raw_payload, hashlib.sha256).hexdigest()
    )

    with Session(database) as session:
        _user, company = _company(session)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="Meta Cloud",
            integration_type=IntegrationType.OFFICIAL.value,
            adapter="whatsapp_cloud",
            external_account_id="102030405060708",
            credentials_json=_credentials().model_dump(),
            config_json={
                "phone_number_id": "109876543210987",
                "coexistence": False,
            },
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        result = service.process_meta_webhook(
            session=session,
            raw_payload=raw_payload,
            signature_header=signature,
        )

        assert result == {"received": True, "processed": 1}
        message = session.exec(
            select(WhatsAppMessage).where(
                WhatsAppMessage.external_id == "wamid.inbound-1"
            )
        ).one()
        conversation = session.get(WhatsAppConversation, message.conversation_id)
        assert message.direction == MessageDirection.INBOUND.value
        assert message.status == MessageStatus.SENT.value
        assert message.content == "Olá"
        assert conversation is not None
        assert conversation.title == "Jane Doe"
        assert verify_webhook_signature(raw_payload, signature, "app-secret")
        assert not verify_webhook_signature(raw_payload, "sha256=invalid", "app-secret")


@pytest.mark.parametrize(
    ("phone_number", "expected"),
    [
        ("+55 75 997136619", "557597136619"),
        ("+55 75 97136619", "557597136619"),
        ("0055 (75) 97136619", "557597136619"),
        ("+55 11 987654321", "5511987654321"),
        ("+1 (202) 555-0123", "12025550123"),
    ],
)
def test_format_phone_number_for_meta(phone_number: str, expected: str) -> None:
    assert format_phone_number_for_meta(phone_number) == expected


def test_format_phone_number_for_meta_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one digit"):
        format_phone_number_for_meta("+ (---)")


def test_delete_cloud_api_template_calls_meta_and_validates(monkeypatch, database) -> None:
    deleted: dict[str, str] = {}

    class FakeMetaClient:
        def __init__(self, credentials) -> None:
            self.credentials = credentials

        def delete_message_template(
            self, *, name: str, hsm_id: str | None = None
        ) -> bool:
            deleted["name"] = name
            deleted["hsm_id"] = hsm_id or ""
            return True

    monkeypatch.setattr(service, "MetaCloudApiClient", FakeMetaClient)

    with Session(database) as session:
        user, company = _company(session)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="Meta Cloud",
            integration_type=IntegrationType.OFFICIAL.value,
            adapter="whatsapp_cloud",
            credentials_json=_credentials().model_dump(),
            config_json={"coexistence": False},
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        service.delete_cloud_api_template(
            session=session,
            integration_id=integration.id,
            current_user=user,
            template_name="appointment_reminder",
            hsm_id="template-1",
        )

        assert deleted == {
            "name": "appointment_reminder",
            "hsm_id": "template-1",
        }


def test_delete_cloud_api_template_requires_cloud_integration(database) -> None:
    with Session(database) as session:
        user, company = _company(session)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="Unofficial",
            integration_type=IntegrationType.UNOFFICIAL.value,
            adapter="test-unofficial",
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        with pytest.raises(HTTPException) as exc:
            service.delete_cloud_api_template(
                session=session,
                integration_id=integration.id,
                current_user=user,
                template_name="any",
            )
        assert exc.value.status_code == 422
