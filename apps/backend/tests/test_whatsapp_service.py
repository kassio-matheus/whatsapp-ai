import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.modules.auth.models import User
from app.modules.companies.models import Company
from app.modules.whatsapp import service
from app.modules.whatsapp.models import (
    IntegrationType,
    MessageDirection,
    WhatsAppContactCreate,
    WhatsAppConversationCreate,
    WhatsAppIntegrationCreate,
    WhatsAppMessageCreate,
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


def _company(session: Session, *, email: str) -> tuple[User, Company]:
    user = User(
        email=email,
        hashed_password="test-password",
        is_super_admin=True,
        is_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    company = Company(name=f"Company {email}", owner_id=user.id)
    session.add(company)
    session.commit()
    session.refresh(company)
    return user, company


def test_whatsapp_resources_crud_and_soft_delete(database) -> None:
    with Session(database) as session:
        user, company = _company(session, email="owner@example.com")
        integration = service.create_integration(
            session=session,
            current_user=user,
            data=WhatsAppIntegrationCreate(
                company_id=company.id,
                name="Official API",
                integration_type=IntegrationType.OFFICIAL,
                adapter="test-official",
                credentials={"token": "not-returned"},
            ),
        )
        contact = service.create_contact(
            session=session,
            current_user=user,
            data=WhatsAppContactCreate(
                integration_id=integration.id,
                phone_number="+5511999999999",
                name="Jane Doe",
            ),
        )
        conversation = service.create_conversation(
            session=session,
            current_user=user,
            data=WhatsAppConversationCreate(
                integration_id=integration.id,
                contact_id=contact.id,
            ),
        )
        message = service.create_message(
            session=session,
            current_user=user,
            data=WhatsAppMessageCreate(
                conversation_id=conversation.id,
                direction=MessageDirection.OUTBOUND,
                content="Hello",
            ),
        )

        assert len(service.list_contacts(session=session, current_user=user)) == 1
        assert len(service.list_conversations(session=session, current_user=user)) == 1
        assert (
            len(
                service.list_messages(
                    session=session,
                    current_user=user,
                    conversation_id=conversation.id,
                )
            )
            == 1
        )

        service.delete_message(
            session=session,
            message_id=message.id,
            current_user=user,
        )
        assert (
            service.list_messages(
                session=session,
                current_user=user,
                conversation_id=conversation.id,
            )
            == []
        )

        service.delete_integration(
            session=session,
            integration_id=integration.id,
            current_user=user,
        )
        assert service.list_integrations(session=session, current_user=user) == []


def test_whatsapp_resources_are_company_scoped(database) -> None:
    with Session(database) as session:
        owner, company = _company(session, email="owner@example.com")
        other_owner, _ = _company(session, email="other-owner@example.com")
        integration = service.create_integration(
            session=session,
            current_user=owner,
            data=WhatsAppIntegrationCreate(
                company_id=company.id,
                name="Private API",
                integration_type=IntegrationType.UNOFFICIAL,
                adapter="test-unofficial",
            ),
        )

        assert (
            service.list_integrations(session=session, current_user=other_owner) == []
        )
        with pytest.raises(HTTPException) as error:
            service.get_integration(
                session=session,
                integration_id=integration.id,
                current_user=other_owner,
            )
        assert error.value.status_code == 404

        with pytest.raises(HTTPException) as error:
            service.list_integrations(
                session=session,
                current_user=other_owner,
                company_id=company.id,
            )
        assert error.value.status_code == 404
