from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Tuple, Optional, Dict
from datetime import date


# =========================
# ① マッチ計算（既存API用）
# =========================

# 求職者（job_seekers 等）→ マッチ計算に使う入力
class CandidateData(BaseModel):
    name: str                                       # 求職者氏名
    desired_job: str                                # 志望職種（job_seekers.desired_job）
    desired_location: str                           # 希望勤務地（job_seekers.desired_location）
    desired_salary: int                             # 希望年収（job_seekers.desired_salary）
    available_start_date: date                      # 稼働可能日（job_seekers.available_start_date）
    work_style_type: str                            # 希望働き方（job_seekers.work_style_type）
    skills: List[str]                               # スキル一覧（job_seeker_skills → skills.name）
    job_preference: str                             # 志望職種の自然文（職種マッチに使用）
    experience_years: float                         # 実務経験年数（job_histories 合算）
    preference_tags: List[str]                      # 志向性タグ（job_seeker_tags → tags.name）
    priority_order: List[str]                       # 優先度の高い評価項目（matching_field/code 等）

# 求人（job_postings 等）→ マッチ計算に使う入力
class JobData(BaseModel):
    job_title: str                                  # 求人職種名（job_postings.title）
    job_location: str                               # 勤務地（job_postings.location）
    salary: int                                     # 年収（単一カラムに対応）
    availability_required: date                     # 稼働開始日（job_postings.start_date）
    work_style_type: str                            # 働き方（job_postings.work_style_type）
    required_skills: List[str]                      # 必須スキル（job_posting_skills → skills.name）
    optional_skills: List[str]                      # 任意スキル
    culture_tags: List[str]                         # 社風タグ（job_posting_tags → tags.name）
    experience_required: Optional[float] = None     # 求める経験年数（必要なら）

# /match のリクエスト・レスポンス
class MatchRequest(BaseModel):
    candidate: CandidateData
    job: JobData

class MatchResponse(BaseModel):
    match_score: float
    message: str
    breakdown: Dict[str, float]  # 例: {"skill_score": 0.82, ...}

# 理由付きレスポンス（/match/by-id-with-reason などで使用）
class MatchWithReasonResponse(MatchResponse):
    reason: str


# ==========================================
# ② DB登録・取得用（JobPosting の作成/取得）
# ==========================================

# 求人スキル（登録用）
class JobPostingSkillCreate(BaseModel):
    skill_id: int                  # skills.id
    required: bool = True
    skill_level: Optional[int] = None

# 求人タグ（登録用）
class JobPostingTagCreate(BaseModel):
    tag_id: int                    # tags.id

# 求人登録（POST /job_postings）
class JobPostingCreate(BaseModel):
    title: str
    location: Optional[str] = None
    salary: Optional[int] = None
    start_date: Optional[date] = None
    work_style_type: Optional[str] = None
    skills: List[JobPostingSkillCreate] = Field(default_factory=list)
    tags: List[JobPostingTagCreate] = Field(default_factory=list)
    # もし industry を使う場合は以下を開ける
    industry: Optional[str] = None

# 求人取得の返却（GET /job_postings/{id}）
class JobPostingOut(BaseModel):
    id: int
    title: str
    location: Optional[str]
    salary: Optional[int]
    start_date: Optional[date]
    work_style_type: Optional[str]
    industry: Optional[str] = None

    class Config:
        from_attributes = True  # SQLAlchemyのORMオブジェクトから作るため


# ==========================================
# ③ DBからIDで読み出してマッチ（/match/by-id 用）
# ==========================================

class MatchByIdRequest(BaseModel):
    job_seeker_id: int
    job_posting_id: int


# ==========================================
# ④ 求職者→求人ランキング（新規）
# ==========================================
class MatchRankingItem(BaseModel):
    job_posting_id: int
    title: str
    score: float
    breakdown: Dict[str, float]

class MatchRankingRequest(BaseModel):
    job_seeker_id: int
    top_k: int = 10

class MatchRankingResponse(BaseModel):
    job_seeker_id: int
    results: List[MatchRankingItem]