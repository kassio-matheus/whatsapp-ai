import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.modules.ai_whatsapp.responder import _generate_and_send
from app.modules.companies.models import Company
from app.modules.whatsapp.events import whatsapp_event_broker
from app.modules.whatsapp.models import (
    MessageDirection,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppIntegration,
    WhatsAppMessage,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        owner = uuid.uuid4()
        company = Company(name="Acme", owner_id=owner)
        db.add(company)
        db.commit()
        db.refresh(company)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="WhatsApp",
            integration_type="official",
            adapter="test-official",
        )
        contact = WhatsAppContact(
            company_id=company.id,
            integration_id=integration.id,
            phone_number="5511999999999",
        )
        db.add(integration)
        db.add(contact)
        db.commit()
        db.refresh(integration)
        db.refresh(contact)
        conversation = WhatsAppConversation(
            company_id=company.id,
            integration_id=integration.id,
            contact_id=contact.id,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        yield db, company, integration, conversation


def _inbound_message(
    session: Session, conversation: WhatsAppConversation, content: str
) -> WhatsAppMessage:
    message = WhatsAppMessage(
        company_id=conversation.company_id,
        integration_id=conversation.integration_id,
        conversation_id=conversation.id,
        direction=MessageDirection.INBOUND.value,
        message_type="text",
        content=content,
        status="sent",
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def _fake_result(response: str = "Boa tarde! Como posso ajudar?"):
    return type("Result", (), {"response": response})()


def test_auto_reply_delivers_exactly_one_message(session, monkeypatch):
    db, _company, integration, conversation = session
    inbound = _inbound_message(
        db, conversation, "quanto custa o plano basico?"
    )

    captured = {}

    def fake_generate_for_company(**kwargs):
        captured["allowed_tools"] = kwargs.get("allowed_tools")
        captured["prompt"] = kwargs.get("prompt")
        return _fake_result()

    monkeypatch.setattr(
        "app.modules.ai.gateway.generate_for_company",
        fake_generate_for_company,
    )

    _generate_and_send(db, inbound, conversation, integration)

    replies = db.exec(
        select(WhatsAppMessage).where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.direction == MessageDirection.OUTBOUND.value,
        )
    ).all()
    drafts = db.exec(
        select(WhatsAppMessage).where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.message_type == "ai",
        )
    ).all()

    assert len(replies) == 1
    assert len(drafts) == 0
    reply = replies[0]
    assert reply.message_type == "text"
    assert reply.metadata_json.get("ai_kind") == "auto_reply"
    assert reply.metadata_json.get("reply_to_message_id") == str(inbound.id)
    assert captured["allowed_tools"] == []
    assert captured["prompt"] == "quanto custa o plano basico?"


def test_auto_reply_does_not_send_when_already_answered(session, monkeypatch):
    db, _company, integration, conversation = session
    inbound = _inbound_message(db, conversation, "segunda mensagem")

    def fake_generate_for_company(**kwargs):
        return _fake_result()

    monkeypatch.setattr(
        "app.modules.ai.gateway.generate_for_company",
        fake_generate_for_company,
    )
    _generate_and_send(db, inbound, conversation, integration)
    _generate_and_send(db, inbound, conversation, integration)

    replies = db.exec(
        select(WhatsAppMessage).where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.direction == MessageDirection.OUTBOUND.value,
        )
    ).all()
    assert len(replies) == 1


def test_auto_reply_empty_response_creates_failure_note(session, monkeypatch):
    db, _company, integration, conversation = session
    inbound = _inbound_message(db, conversation, "mensagem sem resposta")

    def fake_generate_for_company(**kwargs):
        return _fake_result(response="   ")

    monkeypatch.setattr(
        "app.modules.ai.gateway.generate_for_company",
        fake_generate_for_company,
    )
    _generate_and_send(db, inbound, conversation, integration)

    notes = db.exec(
        select(WhatsAppMessage).where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.message_type == "note",
        )
    ).all()
    replies = db.exec(
        select(WhatsAppMessage).where(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.direction == MessageDirection.OUTBOUND.value,
        )
    ).all()
    assert len(notes) == 1
    assert len(replies) == 0


def test_auto_reply_publishes_real_time_event(session, monkeypatch):
    db, company, integration, conversation = session
    inbound = _inbound_message(db, conversation, "evento em tempo real")

    def fake_generate_for_company(**kwargs):
        return _fake_result()

    monkeypatch.setattr(
        "app.modules.ai.gateway.generate_for_company",
        fake_generate_for_company,
    )

    received = []

    def record(event):
        received.append(event.type)

    import queue

    subscriber: queue.Queue = queue.Queue(maxsize=100)
    with whatsapp_event_broker._lock:
        whatsapp_event_broker._subscribers[str(company.id)].add(subscriber)
    original_put = subscriber.put_nowait

    def capture(event):
        record(event)
        original_put(event)

    subscriber.put_nowait = capture

    try:
        _generate_and_send(db, inbound, conversation, integration)
        events = list(received)
        assert "message.created" in events
    finally:
        with whatsapp_event_broker._lock:
            whatsapp_event_broker._subscribers[str(company.id)].discard(subscriber)
            if not whatsapp_event_broker._subscribers[str(company.id)]:
                whatsapp_event_broker._subscribers.pop(str(company.id), None)
