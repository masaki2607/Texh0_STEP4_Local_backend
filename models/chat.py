from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_seeker_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("job_seekers.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    job_seeker = relationship("JobSeeker", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("chat_sessions.id"))
    sender: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text)
    is_ai_generated: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    session = relationship("ChatSession", back_populates="messages")
    references = relationship("ChatMessageReference", back_populates="message", cascade="all, delete-orphan")

class ChatMessageReference(Base):
    __tablename__ = "chat_message_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_messages.id"))
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"))
    field_name: Mapped[str | None] = mapped_column(String(255))
    field_value_snapshot: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    message = relationship("ChatMessage", back_populates="references")
    job_posting = relationship("JobPosting", back_populates="chat_message_references")