from __future__ import annotations
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    job_posting_links = relationship("JobPostingSkill", back_populates="skill", cascade="all, delete-orphan")
    job_seeker_links = relationship("JobSeekerSkill", back_populates="skill", cascade="all, delete-orphan")

class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    job_posting_links = relationship("JobPostingTag", back_populates="tag", cascade="all, delete-orphan")
    job_seeker_links = relationship("JobSeekerTag", back_populates="tag", cascade="all, delete-orphan")

class MatchingPriorityCategory(Base):
    __tablename__ = "matching_priority_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str | None] = mapped_column(String(255))
    label: Mapped[str | None] = mapped_column(String(255))