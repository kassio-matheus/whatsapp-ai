import uuid

from app.modules.whatsapp.events import WhatsAppEventBroker


def test_whatsapp_events_are_scoped_to_the_company() -> None:
    broker = WhatsAppEventBroker()
    company_id = uuid.uuid4()

    with broker.subscribe(company_id) as subscriber:
        broker.publish(
            company_id=company_id,
            event_type="message.created",
            instance_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            message_id=uuid.uuid4(),
        )
        event = subscriber.get_nowait()

    assert event.type == "message.created"
    assert event.company_id == str(company_id)
    assert event.instance_id is not None
    assert event.conversation_id is not None
    assert event.message_id is not None
