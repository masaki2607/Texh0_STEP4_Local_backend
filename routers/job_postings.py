from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import schemas
from models import JobPosting  # JobPostingSkill, JobPostingTag は読み取り専用化で未使用

router = APIRouter(
    prefix="/job_postings",
    tags=["Job Postings"],
)

# ============================================================
# （本番方針）読み取り専用API
# ============================================================

# 求人の一覧（任意・簡易版）。不要ならこの関数を削除してOK
@router.get("/", response_model=list[schemas.JobPostingOut])
def list_job_postings(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    q = db.query(JobPosting).order_by(JobPosting.id.desc()).offset(offset).limit(limit)
    return q.all()

# 求人の取得
@router.get("/{job_id}", response_model=schemas.JobPostingOut)
def read_job_posting(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)  # SQLAlchemy 2系の取得
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


# ============================================================
# （参考／無効化）新規求人の登録
# 本番運用：読み取り専用のため公開しません。
# もし管理用途で使いたくなったら、下記を復活＆認証を付与してください。
# ============================================================
"""
# 新規求人の登録
@router.post("/", response_model=schemas.JobPostingOut)
def create_job_posting(posting: schemas.JobPostingCreate, db: Session = Depends(get_db)):
    # JobPosting 本体
    job = JobPosting(
        title=posting.title,
        location=posting.location,
        salary=posting.salary,                 # 単一 salary
        start_date=posting.start_date,
        work_style_type=posting.work_style_type,
        industry=posting.industry,             # 使用しないなら None のままでOK
    )
    db.add(job)
    db.flush()  # ← job.id を採番

    # skills（schemas → models へのフィールド名マッピング）
    for s in posting.skills:
        db.add(JobPostingSkill(
            job_posting_id=job.id,
            skill_id=s.skill_id,
            required_level=s.skill_level,      # models 側：required_level
            is_mandatory=s.required,           # models 側：is_mandatory
        ))

    # tags
    for t in posting.tags:
        db.add(JobPostingTag(
            job_posting_id=job.id,
            tag_id=t.tag_id,
        ))

    db.commit()
    db.refresh(job)
    return job
"""