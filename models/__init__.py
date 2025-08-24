from database import Base

# 基本マスタ
from .company import Company
from .taxonomy import Skill, Tag, MatchingPriorityCategory

# 求人関連
from .job_posting import JobPosting, JobPostingSkill, JobPostingTag

# 求職者関連
from .job_seeker import (
    JobSeeker,
    JobSeekerSkill,
    JobSeekerTag,
    JobHistory,
    JobSeekerPriority,
)

# チャット・ノート
from .chat import ChatSession, ChatMessage, ChatMessageReference
from .notes import BusinessMeetingNote, InterviewNote

# マッチ結果
from .matching import MatchingScore

__all__ = (
    "Base",
    # 基本マスタ
    "Company",
    "Skill",
    "Tag",
    "MatchingPriorityCategory",
    # 求人
    "JobPosting",
    "JobPostingSkill",
    "JobPostingTag",
    # 求職者
    "JobSeeker",
    "JobSeekerSkill",
    "JobSeekerTag",
    "JobHistory",
    "JobSeekerPriority",
    # チャット・ノート
    "ChatSession",
    "ChatMessage",
    "ChatMessageReference",
    "BusinessMeetingNote",
    "InterviewNote",
    # マッチ結果
    "MatchingScore",
)