from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional

from pydantic import BaseModel  # ← 追加：ReasonRequest/Response 用
import re  # ← /rank-ui の簡易分割で使用

from database import get_db
import schemas
from models import JobPosting, JobSeeker, JobSeekerPriority  # ← 優先度テーブルを参照
from services.matching import (
    match_score_logic,
    # ★ 追加：ランキングサービスを使用
    rank_jobs_for_seeker_service,
)
from rag_utils import generate_match_reason

router = APIRouter(
    prefix="/match",
    tags=["Matching"],
)

# =========================
# 優先度コードの正規化ヘルパー
# -------------------------
# DBの "matching_field" / "category_code" / 関連モデルの "code"
# など、どのカラムが入ってきても最終的に breakdown のキーへ正規化します。
# =========================
def _normalize_priority_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    code = raw.strip().lower()

    # よくありそうな表記ゆれをまとめて受ける
    aliases = {
        # スキル
        "skill": "skill_score",
        "skills": "skill_score",
        "skill_score": "skill_score",

        # 職種名（タイトル）
        "job_title": "job_title_score",
        "title": "job_title_score",
        "job_title_score": "job_title_score",

        # 年収
        "salary": "salary_score",
        "comp": "salary_score",
        "compensation": "salary_score",
        "salary_score": "salary_score",

        # 勤務地
        "location": "location_score",
        "place": "location_score",
        "location_score": "location_score",

        # 稼働開始時期
        "availability": "availability_score",
        "start_date": "availability_score",
        "availability_required": "availability_score",
        "availability_score": "availability_score",

        # 働き方
        "work_style": "work_style_score",
        "workstyle": "work_style_score",
        "work_style_type": "work_style_score",
        "work_style_score": "work_style_score",

        # 志向性/カルチャー
        "preference": "preference_score",
        "culture": "preference_score",
        "tags": "preference_score",
        "preference_score": "preference_score",

        # 経験年数
        "experience": "experience_score",
        "years": "experience_score",
        "experience_required": "experience_score",
        "experience_score": "experience_score",
    }
    return aliases.get(code)


def _fetch_priority_order(db: Session, seeker_id: int) -> List[str]:
    """
    job_seeker_priorities から優先度を昇順で取得し、
    breakdown キーに正規化した配列を返す。
    無ければデフォルト（skill > job_title > salary）。
    """
    order: List[str] = []

    # どのカラム名かは環境差がありうるため、防御的に取得
    rows = (
        db.query(JobSeekerPriority)
        .filter(JobSeekerPriority.job_seeker_id == seeker_id)
        .order_by(
            # よくあるカラム名に順次対応。存在しない場合は order_by なしで all() に。
            getattr(JobSeekerPriority, "priority_order", None)
            or getattr(JobSeekerPriority, "rank", None)
            or getattr(JobSeekerPriority, "sort_order", None)
            or JobSeekerPriority.id  # 最後の砦
        )
        .all()
    )

    for r in rows:
        # 候補になりそうなフィールドからコードを拾う
        raw_code = None
        if hasattr(r, "matching_field") and r.matching_field:
            raw_code = r.matching_field
        elif hasattr(r, "category_code") and r.category_code:
            raw_code = r.category_code
        # リレーションで category がある場合（例：r.category.code）
        elif hasattr(r, "category") and getattr(r, "category") is not None:
            cat = getattr(r, "category")
            if hasattr(cat, "code") and cat.code:
                raw_code = cat.code

        normalized = _normalize_priority_code(raw_code)
        if normalized and normalized not in order:
            order.append(normalized)

    if not order:
        # デフォルト（従来の挙動）
        order = ["skill_score", "job_title_score", "salary_score"]

    return order


# ========== 既存：JSON一発マッチ ==========
@router.post("/", response_model=schemas.MatchResponse)
def match_job(req: schemas.MatchRequest):
    total_score, details = match_score_logic(req.candidate, req.job, req.candidate.priority_order)
    msg = f"{req.candidate.name}さんは「{req.job.job_title}」に{total_score}%マッチしています。"
    return schemas.MatchResponse(match_score=total_score, message=msg, breakdown=details)


# ========== 既存：RAGで理由生成 ==========
class ReasonRequest(BaseModel):
    user_info: str

class ReasonResponse(BaseModel):
    reason: str

@router.post("/generate-reason", response_model=ReasonResponse)
def generate_reason(req: ReasonRequest):
    try:
        explanation = generate_match_reason(req.user_info)
        return ReasonResponse(reason=explanation)
    except Exception as e:
        return ReasonResponse(reason=f"エラーが発生しました: {str(e)}")


# ========== 追加：DBのIDでマッチ計算（/match/by-id） ==========
def _resolve_job_from_db(job: JobPosting) -> dict:
    # 必要ならJOINでskills/tagsの名前解決に拡張可
    required_skills = [f"skill_{s.skill_id}" for s in job.skills if getattr(s, "is_mandatory", False)]
    optional_skills = [f"skill_{s.skill_id}" for s in job.skills if not getattr(s, "is_mandatory", False)]
    culture_tags = [f"tag_{t.tag_id}" for t in job.tags]

    return {
        "job_title": job.title,
        "job_location": job.location or "",
        "salary": job.salary or 0,
        "availability_required": job.start_date or date.today(),
        "work_style_type": job.work_style_type or "",
        "required_skills": required_skills,
        "optional_skills": optional_skills,
        "culture_tags": culture_tags,
        "experience_required": None,
    }

def _resolve_candidate_from_db(seeker: JobSeeker, db: Session) -> dict:
    """
    ★ ここが変更点：
      - これまで固定だった priority_order を、
        job_seeker_priorities から取得して反映。
    """
    skills = [f"skill_{s.skill_id}" for s in seeker.skills]
    tags = [f"tag_{t.tag_id}" for t in seeker.tags]
    # TODO: priorities を job_seeker_priorities から取得して並べ替え（実装済み）
    priority_order = _fetch_priority_order(db, seeker.id)

    return {
        "name": seeker.name,
        "desired_job": seeker.desired_job or "",
        "desired_location": seeker.desired_location or "",
        "desired_salary": seeker.desired_salary or 0,
        "available_start_date": seeker.available_start_date or date.today(),
        "work_style_type": seeker.work_style_type or "",
        "skills": skills,
        "job_preference": seeker.desired_job or "",
        "experience_years": 0.0,
        "preference_tags": tags,
        "priority_order": priority_order,
    }

@router.post("/by-id", response_model=schemas.MatchResponse)
def match_by_id(req: schemas.MatchByIdRequest, db: Session = Depends(get_db)):
    seeker = db.get(JobSeeker, req.job_seeker_id)
    job = db.get(JobPosting, req.job_posting_id)
    if not seeker or not job:
        raise HTTPException(status_code=404, detail="job_seeker or job_posting not found")

    # ★ DB から priority_order を反映するために db を渡す
    candidate = schemas.CandidateData(**_resolve_candidate_from_db(seeker, db))
    jobdata = schemas.JobData(**_resolve_job_from_db(job))

    total_score, details = match_score_logic(candidate, jobdata, candidate.priority_order)
    msg = f"{candidate.name}さんは「{jobdata.job_title}」に{total_score}%マッチしています。"
    return schemas.MatchResponse(match_score=total_score, message=msg, breakdown=details)


# ========== 追加：DBのIDでマッチ計算＋理由生成（/match/by-id-with-reason） ==========
@router.post("/by-id-with-reason", response_model=schemas.MatchWithReasonResponse)
def match_by_id_with_reason(req: schemas.MatchByIdRequest, db: Session = Depends(get_db)):
    seeker = db.get(JobSeeker, req.job_seeker_id)
    job = db.get(JobPosting, req.job_posting_id)
    if not seeker or not job:
        raise HTTPException(status_code=404, detail="job_seeker or job_posting not found")

    candidate = schemas.CandidateData(**_resolve_candidate_from_db(seeker, db))
    jobdata = schemas.JobData(**_resolve_job_from_db(job))

    total_score, details = match_score_logic(candidate, jobdata, candidate.priority_order)
    msg = f"{candidate.name}さんは「{jobdata.job_title}」に{total_score}%マッチしています。"

    user_info = (
        f"{candidate.name}さんは{candidate.desired_location}希望、働き方は{candidate.work_style_type}。"
        f"経験年数は{candidate.experience_years}年。スキル: {', '.join(candidate.skills)}。"
        f"応募ポジション: {jobdata.job_title}。"
    )
    reason_text = generate_match_reason(user_info)

    return schemas.MatchWithReasonResponse(
        match_score=total_score, message=msg, breakdown=details, reason=reason_text
    )


# ========== 追加：求人ランキング（/match/rankings） ==========
@router.post("/rankings", response_model=schemas.MatchRankingResponse)
def get_rankings(req: schemas.MatchRankingRequest, db: Session = Depends(get_db)):
    """
    指定した求職者IDに対して、全求人をスコアリングし上位を返す。
    パフォーマンス最適化（事前フィルタやLIMIT）は必要に応じて強化予定。
    """
    try:
        return rank_jobs_for_seeker_service(
            seeker_id=req.job_seeker_id,
            db=db,
            top_k=req.top_k or 10,
        )
    except ValueError as e:
        # services 側で not found の場合は ValueError を投げる想定
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 想定外エラー
        raise HTTPException(status_code=500, detail=f"ranking failed: {e}")


# ========== 追加：フロント用の薄い出力（/match/rank-ui） ==========
@router.post("/rank-ui")
def rank_ui(req: schemas.MatchRankingRequest, db: Session = Depends(get_db)):
    """
    フロントの MatchingResult.tsx に合わせた整形出力。
    - company/name, industry, location は関連が無ければフォールバック文字列に。
    - salary は万円表示に変換（low/high が無ければ単一 salary を流用）。
    """
    try:
        # 1) 生データ（内部フォーマット）を取得
        rank_resp = rank_jobs_for_seeker_service(
            seeker_id=req.job_seeker_id,
            db=db,
            top_k=req.top_k or 10,
        )

        # 2) 整形: Pydanticモデルなので属性アクセスで取り出す
        def _to_man(y):
            """年収(円)を万円に丸める。None/変換失敗は None。"""
            if y is None:
                return None
            try:
                return int(y) // 10000
            except Exception:
                return None

        def _reason_to_list(txt: Optional[str]) -> list[str]:
            """理由テキストを箇条書き用にざっくり分割（無ければ空）。"""
            if not txt:
                return []
            parts = [p.strip() for p in re.split(r"[。.\n]", txt) if p.strip()]
            return parts[:5]

        def _top_keys(breakdown: Optional[dict]) -> list[str]:
            """breakdown の上位要素名を短いラベルにして返す（UIの bullets 用）"""
            if not breakdown:
                return []
            items = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
            keymap = {
                "skill_score": "スキル適合",
                "job_title_score": "職種マッチ",
                "salary_score": "年収マッチ",
                "location_score": "勤務地一致",
                "availability_score": "稼働時期",
                "work_style_score": "働き方相性",
                "preference_score": "志向・カルチャー",
                "experience_score": "経験年数",
            }
            return [keymap.get(k, k) for k, _ in items]

        out = {"matchedJobs": []}

        for it in rank_resp.results:
            # ← 重要：Pydanticモデルなので辞書ではなく属性アクセス！
            jp = db.get(JobPosting, it.job_posting_id)
            if not jp:
                continue

            # 会社情報（関連が無ければフォールバック）
            company = getattr(jp, "company", None)
            company_name = getattr(company, "name", None) or "（企業名不明）"
            industry = getattr(company, "industry", None) or "—"
            location = jp.location or "—"

            # ポジション名（title 無ければID）
            position = jp.title or f"求人ID: {jp.id}"

            # 年収（low/high があれば優先、無ければ単一 salary）
            salary_min = _to_man(getattr(jp, "salary_low", None))
            salary_max = _to_man(getattr(jp, "salary_high", None))
            if salary_min is None and salary_max is None:
                one = _to_man(getattr(jp, "salary", None))
                salary_min = one
                salary_max = one

            out["matchedJobs"].append(
                {
                    "id": jp.id,
                    "company": {
                        "name": company_name,
                        "industry": industry,
                        "location": location,
                    },
                    "position": position,
                    "salary": {
                        "min": salary_min or 0,
                        "max": salary_max or (salary_min or 0),
                    },
                    "matchingScore": it.score,
                    "matchingReasons": _reason_to_list(getattr(it, "reason", None)),
                    "requirements": _top_keys(getattr(it, "breakdown", None)),
                    "benefits": [],  # UI用の空配列（必要なら後で拡張）
                }
            )

        return out

    except ValueError as e:
        # services 側で not found など
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 想定外エラー
        raise HTTPException(status_code=500, detail=f"rank-ui failed: {e}")