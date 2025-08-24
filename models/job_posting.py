from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from datetime import date, datetime

from sqlalchemy import Integer, String, Date, DateTime, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    # 型ヒント用（実行時には読み込まれない）
    from .company import Company
    from .taxonomy import Skill, Tag
    from .notes import BusinessMeetingNote, InterviewNote
    from .chat import ChatMessageReference
    from .matching import MatchingScore

class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    salary: Mapped[Optional[int]] = mapped_column(Integer)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    work_style_type: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("companies.id"))
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="job_postings")

    # --- 1対多 ---
    skills: Mapped[List["JobPostingSkill"]] = relationship(
        "JobPostingSkill", back_populates="job_posting", cascade="all, delete-orphan"
    )
    tags: Mapped[List["JobPostingTag"]] = relationship(
        "JobPostingTag", back_populates="job_posting", cascade="all, delete-orphan"
    )
    business_meeting_notes: Mapped[List["BusinessMeetingNote"]] = relationship(
        "BusinessMeetingNote", back_populates="job_posting", cascade="all, delete-orphan"
    )
    chat_message_references: Mapped[List["ChatMessageReference"]] = relationship(
        "ChatMessageReference", back_populates="job_posting", cascade="all, delete-orphan"
    )
    interview_notes: Mapped[List["InterviewNote"]] = relationship(
        "InterviewNote", back_populates="job_posting", cascade="all, delete-orphan"
    )
    matching_scores: Mapped[List["MatchingScore"]] = relationship(
        "MatchingScore", back_populates="job_posting", cascade="all, delete-orphan"
    )

class JobPostingSkill(Base):
    __tablename__ = "job_posting_skills"
    my_row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"), nullable=False)
    required_level: Mapped[Optional[int]] = mapped_column(Integer)
    is_mandatory: Mapped[Optional[bool]] = mapped_column(Boolean)

    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="job_posting_links")

class JobPostingTag(Base):
    __tablename__ = "job_posting_tags"
    my_row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_postings.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), nullable=False)

    job_posting: Mapped["JobPosting"] = relationship("JobPosting", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="job_posting_links")