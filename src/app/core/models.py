# core/models.py
import uuid
from datetime import datetime
from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class MapMeta(Base):
    __tablename__ = "map_meta"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    rows: Mapped[int]
    cols: Mapped[int]

class TileRow(Base):
    __tablename__ = "tiles"
    x: Mapped[int] = mapped_column(primary_key=True)
    y: Mapped[int] = mapped_column(primary_key=True)
    walkable: Mapped[bool]
    dirty: Mapped[bool]

class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime]
    state: Mapped[str]
    robot_model: Mapped[str]
    submitted_actions: Mapped[int]
    successful_steps: Mapped[int]
    cleaned_tiles: Mapped[list] = mapped_column(JSON)
    final_position: Mapped[dict] = mapped_column(JSON)
    duration_ms: Mapped[int]
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)