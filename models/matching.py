from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, Float, JSON, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class MatchingScore(Base):
    __tablename__ = "matching_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"))
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"))
    score: Mapped[Optional[float]] = mapped_column(Float)
    breakdown: Mapped[dict | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    job_seeker = relationship("JobSeeker", back_populates="matching_scores")
    job_posting = relationship("JobPosting", back_populates="matching_scores")