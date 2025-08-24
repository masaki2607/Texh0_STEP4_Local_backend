from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class BusinessMeetingNote(Base):
    __tablename__ = "business_meeting_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"), nullable=False)
    meeting_date: Mapped[Optional[date]] = mapped_column(Date)
    recorded_by: Mapped[Optional[str]] = mapped_column(String(255))
    job_mission: Mapped[Optional[str]] = mapped_column(Text)
    ideal_candidate: Mapped[Optional[str]] = mapped_column(Text)
    org_structure: Mapped[Optional[str]] = mapped_column(Text)
    business_description: Mapped[Optional[str]] = mapped_column(Text)
    business_challenges: Mapped[Optional[str]] = mapped_column(Text)
    revenue_model: Mapped[Optional[str]] = mapped_column(Text)
    business_as_is: Mapped[Optional[str]] = mapped_column(Text)
    business_to_be: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    job_posting = relationship("JobPosting", back_populates="business_meeting_notes")

class InterviewNote(Base):
    __tablename__ = "interview_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"), nullable=False)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    interview_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    job_seeker = relationship("JobSeeker", back_populates="interview_notes")
    job_posting = relationship("JobPosting", back_populates="interview_notes")