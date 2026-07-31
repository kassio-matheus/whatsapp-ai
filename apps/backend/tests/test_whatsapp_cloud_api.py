import hashlib
import hmac
import json
import uuid

import pytest
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
    WhatsAppConversation,
    WhatsAppIntegration,
    WhatsAppMessage,
)


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

    result = client.send_message(
        to="5511999999999",
        message=WhatsAppMessage(
            company_id=uuid.uuid4(),
            integration_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            direction=MessageDirection.OUTBOUND.value,
            content="Hello from Cloud API",
        ),
    )
    assert result.external_id == "wamid.outbound-1"
    assert requests[3][0] == "POST"
    assert requests[3][1].endswith("/109876543210987/messages")
    assert json.loads(requests[3][2] or b"{}")["to"] == "5511999999999"

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
    image_payload = json.loads(requests[4][2] or b"{}")
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
    interactive_payload = json.loads(requests[5][2] or b"{}")
    assert interactive_payload["interactive"]["type"] == "button"


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
    signature = "sha256=" + hmac.new(
        b"app-secret", raw_payload, hashlib.sha256
    ).hexdigest()

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
