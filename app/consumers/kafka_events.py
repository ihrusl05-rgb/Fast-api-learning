import asyncio
import json
import os
from contextlib import suppress

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from app.database.database import engine, new_session
from app.models.models import EventLog


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPICS = [
    topic.strip()
    for topic in os.getenv(
        "KAFKA_TOPICS",
        os.getenv("KAFKA_TOPIC", "partner_changes,partner_changes.partner_changes"),
    ).split(",")
    if topic.strip()
]
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "partner-events-consumer")


def decode_message_key(raw_key: bytes | None) -> str | None:
    if raw_key is None:
        return None
    return raw_key.decode("utf-8", errors="replace")


def parse_payload(raw_payload: bytes) -> tuple[str, str | None, str | None, str | None]:
    payload = raw_payload.decode("utf-8", errors="replace")

    with suppress(json.JSONDecodeError):
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            subject = parsed.get("subject")
            action = parsed.get("action")
            table_name = parsed.get("table") or parsed.get("table_name")
            payload = json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)
            return payload, subject, action, table_name

    return payload, None, None, None


async def persist_event(message) -> None:
    payload, subject, action, table_name = parse_payload(message.value)

    async with new_session() as session:
        existing_event = await session.scalar(
            select(EventLog.id).where(
                EventLog.topic == message.topic,
                EventLog.partition == message.partition,
                EventLog.offset == message.offset,
            )
        )
        if existing_event is not None:
            return

        session.add(
            EventLog(
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                message_key=decode_message_key(message.key),
                subject=subject,
                action=action,
                table_name=table_name,
                payload=payload,
            )
        )
        await session.commit()


async def consume() -> None:
    consumer = AIOKafkaConsumer(
        *KAFKA_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    await consumer.start()
    try:
        async for message in consumer:
            await persist_event(message)
    finally:
        await consumer.stop()
        await engine.dispose()


def main() -> None:
    asyncio.run(consume())


if __name__ == "__main__":
    main()
