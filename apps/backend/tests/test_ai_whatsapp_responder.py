import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.modules.ai_whatsapp.responder import _recent_context
from app.modules.companies.models import Company
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
        company = Company(name="Acme", owner_id=uuid.uuid4())
        db.add(company)
        db.commit()
        db.refresh(company)
        integration = WhatsAppIntegration(
            company_id=company.id,
            name="WhatsApp",
            integration_type="official",
            adapter="meta_cloud_api",
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
        yield db, conversation


def _message(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    content: str,
    direction: str = MessageDirection.INBOUND.value,
) -> WhatsAppMessage:
    message = WhatsAppMessage(
        company_id=conversation.company_id,
        integration_id=conversation.integration_id,
        conversation_id=conversation.id,
        direction=direction,
        message_type="text",
        content=content,
        status="sent",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def test_recent_context_excludes_the_message_being_answered(session):
    db, conversation = session
    older = _message(db, conversation, content="ola, quanto custa?")
    current = _message(db, conversation, content="tem desconto?")

    context = _recent_context(
        session=db,
        conversation_id=conversation.id,
        exclude_message_id=current.id,
    )

    contents = [item["content"] for item in context]
    assert current.content not in contents
    assert older.content in contents


def test_recent_context_without_exclusion_keeps_all_messages(session):
    db, conversation = session
    _message(db, conversation, content="primeira")
    _message(db, conversation, content="segunda")

    context = _recent_context(session=db, conversation_id=conversation.id)

    contents = [item["content"] for item in context]
    assert contents == ["primeira", "segunda"]


def test_recent_context_orders_oldest_first(session):
    db, conversation = session
    _message(db, conversation, content="um")
    _message(db, conversation, content="dois")
    _message(db, conversation, content="tres")

    context = _recent_context(session=db, conversation_id=conversation.id)

    assert [item["content"] for item in context] == ["um", "dois", "tres"]
