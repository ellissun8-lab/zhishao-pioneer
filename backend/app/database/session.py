from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from ..ontology.models import Event
from .models import Base, EventRecord

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "zhishao.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

REQUIRED_COLUMNS = {"subject_id", "confidence"}


def init_database() -> None:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    inspector = inspect(engine)
    if inspector.has_table(EventRecord.__tablename__):
        columns = {column["name"] for column in inspector.get_columns(EventRecord.__tablename__)}
        if not REQUIRED_COLUMNS <= columns:
            # 旧结构审计表缺少 subject_id/confidence 列；审计数据为可再生的演示日志，直接重建
            with engine.begin() as connection:
                connection.execute(text(f"DROP TABLE {EventRecord.__tablename__}"))
    Base.metadata.create_all(engine)


def record_event(event: Event) -> None:
    with Session(engine) as session:
        if session.query(EventRecord).filter_by(event_id=event.id).first():
            return
        session.add(
            EventRecord(
                event_id=event.id,
                event_type=event.type.value,
                subject_id=event.subject_id,
                source=event.source,
                confidence=event.confidence,
                occurred_at=event.timestamp,
                payload_json=event.model_dump_json(),
            )
        )
        session.commit()


def query_events(limit: int = 50) -> list[dict[str, object]]:
    with Session(engine) as session:
        records = session.query(EventRecord).order_by(EventRecord.id.desc()).limit(limit).all()
        return [
            {
                "event_id": record.event_id,
                "event_type": record.event_type,
                "subject_id": record.subject_id,
                "source": record.source,
                "confidence": record.confidence,
                "timestamp": record.occurred_at.isoformat() if record.occurred_at else None,
                "payload": record.payload_json,
            }
            for record in records
        ]
