from __future__ import annotations

import os
from datetime import date
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

# ====== 自作モジュール ======
# （models は name 解決に Skill/Tag などの relationship を使う）
from models import (
    JobPosting, JobPostingSkill, JobPostingTag,
    JobSeeker, JobSeekerSkill, JobSeekerTag,
    MatchingScore,  # ← 任意：結果保存用
)
from schemas import (
    CandidateData, JobData,
    MatchResponse, MatchWithReasonResponse,
    # ★ ランキング用のスキーマ
    MatchRankingItem, MatchRankingResponse,
)

# RAGで理由生成
# （utils/rag_utils.py が無い場合でも動くようにフォールバック）
try:
    from rag_utils import generate_match_reason  # type: ignore
except Exception:
    def generate_match_reason(user_info: str) -> str:  # type: ignore
        return f"求職者情報に基づいて、おおむねスキル・勤務地・希望年収・稼働時期が合致しています。({user_info[:120]}...)"

# ====== 類似度モデル ======
# （SBERT の読み込み・利用は本ファイル側で行う。メモリ事情により無効化可能）
_ENABLE_SBERT = os.getenv("ENABLE_SBERT", "").lower() in ("1", "true", "yes")

if _ENABLE_SBERT:
    try:
        from sentence_transformers import SentenceTransformer, util
        _sbert_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        _SBERT_AVAILABLE = True
    except Exception:
        _sbert_model = None
        _SBERT_AVAILABLE = False
else:
    _sbert_model = None
    _SBERT_AVAILABLE = False


# ---------- 共通ユーティリティ ----------
# SBERTによるテキスト類似度計算 
def sbert_similarity(text1: str, text2: str) -> float:
    """
    SBERTが有効ならコサイン類似度（0〜1相当）、
    無効なら簡易Jaccard類似度（単語の集合一致：0〜1）でフェールバック。
    """
    if _SBERT_AVAILABLE and _sbert_model is not None:
        emb1 = _sbert_model.encode(text1, convert_to_tensor=True)
        emb2 = _sbert_model.encode(text2, convert_to_tensor=True)
        return float(util.pytorch_cos_sim(emb1, emb2).item())

    # フェールバック：Jaccard っぽい簡易スコア（0.0〜1.0）
    set1 = set(text1.split())
    set2 = set(text2.split())
    if not set1 or not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return inter / union


# 優先度に応じた重み付けを返す
def calculate_weight(field: str, priority_list: List[str]) -> float:
    if field not in priority_list:
        return 1.0
    rank = priority_list.index(field)
    return 1.5 if rank == 0 else 1.3 if rank == 1 else 1.1 if rank == 2 else 1.0


# ---------- マッチングロジック本体 ----------
def match_score_logic(candidate: CandidateData, job: JobData, priority_order: List[str]) -> Tuple[float, Dict[str, float]]:
    breakdown: Dict[str, float] = {}
    weighted_scores: List[float] = []
    weights: List[float] = []

    # ① スキル適合度（SBERT）
    skills1 = " ".join(candidate.skills)
    # ↓ job.required_skills / job.optional_skills はそのまま（DB解決側で生成）
    skills2 = " ".join(job.required_skills + job.optional_skills)
    skill_score = sbert_similarity(skills1, skills2)
    breakdown["skill_score"] = round(skill_score, 2)

    # ② 職種マッチ度（SBERT）
    job_score = sbert_similarity(candidate.job_preference, job.job_title)
    breakdown["job_title_score"] = round(job_score, 2)

    # ③ 経験年数（最低1年未満は0、求人側Noneなら満点、差で補正）
    if candidate.experience_years < 1:
        experience_score = 0.0
    elif getattr(job, "experience_required", None) is None:
        experience_score = 1.0
    else:
        gap = job.experience_required - candidate.experience_years  # type: ignore[arg-type]
        experience_score = 1.0 if gap <= 0 else (1.0 - gap / 6.0) if gap <= 3 else 0.5
    breakdown["experience_score"] = round(experience_score, 2)

    # ④ 勤務地（完全一致）
    breakdown["location_score"] = 1.0 if candidate.desired_location == job.job_location else 0.0

    # ⑤ 年収希望（単一カラム salary に対応）
    #   近いほど高スコア、希望年収が提示年収を下回る場合は僅かにプラス補正
    offer = getattr(job, "salary", 0) or 0
    if offer <= 0:
        salary_score = 0.0
    else:
        gap = abs(candidate.desired_salary - offer)
        # 20万円差で0.0になるスケール（調整可）
        salary_score = max(0.0, 1.0 - gap / 200.0)
        if candidate.desired_salary <= offer:
            salary_score = min(1.0, salary_score * 1.05)
    breakdown["salary_score"] = round(min(salary_score, 1.0), 2)

    # ⑥ 志向性マッチ（SBERT）
    tags1 = " ".join(candidate.preference_tags)
    tags2 = " ".join(job.culture_tags)
    preference_score = sbert_similarity(tags1, tags2) if tags1 and tags2 else 0.0
    breakdown["preference_score"] = round(preference_score, 2)

    # ⑦ 稼働可能時期（30日以内満点）
    days_diff = (job.availability_required - candidate.available_start_date).days
    avail_score = 1.0 if days_diff <= 30 else 0.7 if days_diff <= 90 else 0.3
    breakdown["availability_score"] = round(avail_score, 2)

    # ⑧ 働き方希望（SBERT）
    work_score = sbert_similarity(candidate.work_style_type, job.work_style_type) \
        if candidate.work_style_type and job.work_style_type else 0.0
    breakdown["work_style_score"] = round(work_score, 2)

    # 重み付き平均
    for field, value in breakdown.items():
        w = calculate_weight(field, candidate.priority_order)
        weighted_scores.append(value * w)
        weights.append(w)

    total_score = (sum(weighted_scores) / sum(weights) if weights else 0.0) * 100
    return round(total_score, 2), breakdown


# ------ DB → Pydantic 変換ヘルパー（/match/by-id 系で利用） ------
def resolve_job_from_db(job: JobPosting) -> Dict:
    """
    JobPosting（ORM） → JobData（dict）
    skills/tags は **name** を relationship から解決して渡す。
    """
    required_skill_names: List[str] = []
    optional_skill_names: List[str] = []
    for link in job.skills:  # JobPostingSkill
        name = link.skill.name if getattr(link, "skill", None) else f"skill_{link.skill_id}"
        if getattr(link, "is_mandatory", False):
            required_skill_names.append(name)
        else:
            optional_skill_names.append(name)

    culture_tags = [
        (t.tag.name if getattr(t, "tag", None) else f"tag_{t.tag_id}")
        for t in job.tags  # JobPostingTag
    ]

    return {
        "job_title": job.title or "",
        "job_location": job.location or "",
        "salary": job.salary or 0,
        "availability_required": job.start_date or date.today(),
        "work_style_type": job.work_style_type or "",
        "required_skills": required_skill_names,
        "optional_skills": optional_skill_names,
        "culture_tags": culture_tags,
        "experience_required": None,  # 必要なら別テーブルから解決
    }


def resolve_candidate_from_db(seeker: JobSeeker) -> Dict:
    """
    JobSeeker（ORM） → CandidateData（dict）
    skills/tags は **name** を解決。経験年数は job_histories を合算。
    """
    skill_names = [
        (s.skill.name if getattr(s, "skill", None) else f"skill_{s.skill_id}")
        for s in seeker.skills  # JobSeekerSkill
    ]
    tag_names = [
        (t.tag.name if getattr(t, "tag", None) else f"tag_{t.tag_id}")
        for t in seeker.tags  # JobSeekerTag
    ]

    total_years = 0.0
    for h in getattr(seeker, "histories", []):  # JobHistory
        yrs = h.years_of_experience or 0
        try:
            total_years += float(yrs)
        except Exception:
            pass

    # TODO: prioritiesをjob_seeker_prioritiesから取得して、matching_field順に並べる
    priority_order = ["skill_score", "job_title_score", "salary_score"]

    return {
        "name": seeker.name,
        "desired_job": seeker.desired_job or "",
        "desired_location": seeker.desired_location or "",
        "desired_salary": seeker.desired_salary or 0,
        "available_start_date": seeker.available_start_date or date.today(),
        "work_style_type": seeker.work_style_type or "",
        "skills": skill_names,
        "job_preference": seeker.desired_job or "",
        "experience_years": float(total_years),
        "preference_tags": tag_names,
        "priority_order": priority_order,
    }


# ------ ルーターから呼ぶサービス層の関数（副作用少なめ） ------
def match_by_id_service(seeker_id: int, job_id: int, db: Session) -> MatchResponse:
    seeker = db.get(JobSeeker, seeker_id)
    job = db.get(JobPosting, job_id)
    if not seeker or not job:
        # ルーター側でHTTPExceptionに変換する想定でもOK。ここではシンプルにValueError。
        raise ValueError("job_seeker or job_posting not found")

    cand_dict = resolve_candidate_from_db(seeker)
    job_dict = resolve_job_from_db(job)

    candidate = CandidateData(**cand_dict)
    jobdata = JobData(**job_dict)

    total_score, details = match_score_logic(candidate, jobdata, candidate.priority_order)

    # 任意：matching_scores へ保存（失敗してもレスポンスは返す）
    try:
        db.add(MatchingScore(
            job_seeker_id=seeker.id,
            job_posting_id=job.id,
            score=total_score,
            breakdown=details,
            explanation=None,
        ))
        db.commit()
    except Exception:
        db.rollback()

    msg = f"{candidate.name}さんは「{jobdata.job_title}」に{total_score}%マッチしています。"
    return MatchResponse(match_score=total_score, message=msg, breakdown=details)


def match_by_id_with_reason_service(seeker_id: int, job_id: int, db: Session) -> MatchWithReasonResponse:
    seeker = db.get(JobSeeker, seeker_id)
    job = db.get(JobPosting, job_id)
    if not seeker or not job:
        raise ValueError("job_seeker or job_posting not found")

    cand_dict = resolve_candidate_from_db(seeker)
    job_dict = resolve_job_from_db(job)

    candidate = CandidateData(**cand_dict)
    jobdata = JobData(**job_dict)

    total_score, details = match_score_logic(candidate, jobdata, candidate.priority_order)
    msg = f"{candidate.name}さんは「{jobdata.job_title}」に{total_score}%マッチしています。"

    # RAG用の簡易プロンプト（将来は job.description なども含めて強化）
    user_info = (
        f"{candidate.name}さんは{candidate.desired_location}希望、働き方は{candidate.work_style_type}。"
        f"経験年数は{candidate.experience_years}年。スキル: {', '.join(candidate.skills)}。"
        f"応募ポジション: {jobdata.job_title}。"
    )
    reason_text = generate_match_reason(user_info)

    # 任意：matching_scores へ保存（理由付き）
    try:
        db.add(MatchingScore(
            job_seeker_id=seeker.id,
            job_posting_id=job.id,
            score=total_score,
            breakdown=details,
            explanation=reason_text,
        ))
        db.commit()
    except Exception:
        db.rollback()

    return MatchWithReasonResponse(
        match_score=total_score,
        message=msg,
        breakdown=details,
        reason=reason_text,
    )


# ------ 求職者に対する求人ランキング（新規） ------
def rank_jobs_for_seeker_service(seeker_id: int, db: Session, top_k: int = 10) -> MatchRankingResponse:
    """
    指定した求職者IDに対して、全求人をスコアリングし、上位 top_k 件を返す。
    パフォーマンス最適化（フィルタやLIMIT）は後で強化可能。まずは全件評価でOK。
    """
    seeker = db.get(JobSeeker, seeker_id)
    if not seeker:
        raise ValueError("job_seeker not found")

    # 求職者をPydanticへ
    cand_dict = resolve_candidate_from_db(seeker)
    candidate = CandidateData(**cand_dict)

    # 全求人を取得（必要なら「location一致」「業界一致」など前処理で絞り込み可能）
    jobs = db.query(JobPosting).all()

    scored: List[MatchRankingItem] = []
    for job in jobs:
        job_dict = resolve_job_from_db(job)
        jobdata = JobData(**job_dict)

        score, breakdown = match_score_logic(candidate, jobdata, candidate.priority_order)
        scored.append(
            MatchRankingItem(
                job_posting_id=job.id,
                title=job.title or "",
                score=score,
                breakdown=breakdown,
            )
        )

    # スコア降順にソートして上位 top_k
    scored.sort(key=lambda x: x.score, reverse=True)
    results = scored[: max(1, top_k)]

    return MatchRankingResponse(job_seeker_id=seeker_id, results=results)