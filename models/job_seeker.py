from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Integer, String, Date, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class JobSeeker(Base):
    __tablename__ = "job_seekers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(255))
    desired_job: Mapped[Optional[str]] = mapped_column(String(255))
    desired_industry: Mapped[Optional[str]] = mapped_column(String(255))
    desired_location: Mapped[Optional[str]] = mapped_column(String(255))
    desired_salary: Mapped[Optional[int]] = mapped_column(Integer)
    available_start_date: Mapped[Optional[date]] = mapped_column(Date)
    work_style_type: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    skills = relationship("JobSeekerSkill", back_populates="job_seeker", cascade="all, delete-orphan")
    tags = relationship("JobSeekerTag", back_populates="job_seeker", cascade="all, delete-orphan")
    priorities = relationship("JobSeekerPriority", back_populates="job_seeker", cascade="all, delete-orphan")
    histories = relationship("JobHistory", back_populates="job_seeker", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="job_seeker", cascade="all, delete-orphan")
    interview_notes = relationship("InterviewNote", back_populates="job_seeker", cascade="all, delete-orphan")
    matching_scores = relationship("MatchingScore", back_populates="job_seeker", cascade="all, delete-orphan")

class JobSeekerSkill(Base):
    __tablename__ = "job_seeker_skills"
    my_row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"), nullable=False)
    proficiency_level: Mapped[int | None] = mapped_column(Integer)

    job_seeker = relationship("JobSeeker", back_populates="skills")
    skill = relationship("Skill", back_populates="job_seeker_links")

class JobSeekerTag(Base):
    __tablename__ = "job_seeker_tags"
    my_row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), nullable=False)

    job_seeker = relationship("JobSeeker", back_populates="tags")
    tag = relationship("Tag", back_populates="job_seeker_links")

class JobSeekerPriority(Base):
    __tablename__ = "job_seeker_priorities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"), nullable=False)
    priority_rank: Mapped[int | None] = mapped_column(Integer)
    priority_category: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    job_seeker = relationship("JobSeeker", back_populates="priorities")

class JobHistory(Base):
    __tablename__ = "job_histories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_seeker_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_seekers.id"), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(length=2**31 - 1))  # Text 互換

    job_seeker = relationship("JobSeeker", back_populates="histories")