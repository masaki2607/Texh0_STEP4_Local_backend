from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# ====== 自作モジュール ======
# （ルーターに分割：求人CRUDとマッチングAPI）
from routers.job_postings import router as job_postings_router
from routers.matching import router as matching_router

# RAGで理由生成
# （実体は routers/matching.py 側で使用。ここでは import しない）
# from rag_utils import generate_match_reason

# ====== 類似度モデル ======
# （SBERT の読み込み・利用は services/matching.py 側に委譲）
# from sentence_transformers import SentenceTransformer, util

app = FastAPI(
    title="OneView Matching API",
    version="1.0.0",
)

# CORS（Next.jsからの呼び出し許可）
# 環境変数 ALLOW_ORIGINS（カンマ区切り）で上書き可能にする
_env_origins = os.getenv("ALLOW_ORIGINS")
_allow_origins = (
    [o.strip() for o in _env_origins.split(",")] if _env_origins else ["http://localhost:3000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,  # 必要に応じて本番ドメインを追加
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SBERTモデル（多言語）
# ※ 以前は main.py でモデルをロードしていましたが、
#    現在は routers / services に分割し、そこで必要に応じて読み込みます。
# try:
#     sbert_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
#     _SBERT_AVAILABLE = True
# except Exception:
#     sbert_model = None
#     _SBERT_AVAILABLE = False

# ---------- 共通ユーティリティ ----------
# SBERTによるテキスト類似度計算 
# ※ 実装は services/matching.py に移動しました
# def sbert_similarity(...): ...

# 優先度に応じた重み付けを返す
# ※ 実装は services/matching.py に移動しました
# def calculate_weight(...): ...

# ---------- マッチングロジック本体 ----------
# ※ 実装は services/matching.py に移動しました
# def match_score_logic(...): ...

# ========== 既存：JSON一発マッチ ==========
# ※ エンドポイント実装は routers/matching.py に移動しました
# @app.post("/match", ...)

# ========== 既存：RAGで理由生成 ==========
# ※ エンドポイント実装は routers/matching.py に移動しました
# @app.post("/generate-reason", ...)

# ========== 追加：求人の登録/取得 CRUD ==========
# ※ エンドポイント実装は routers/job_postings.py に移動しました
# @app.post("/job_postings", ...)
# @app.get("/job_postings/{job_id}", ...)

# ========== 追加：DBのIDでマッチ計算（/match/by-id） ==========
# ※ エンドポイント実装は routers/matching.py に移動しました

# ========== 追加：DBのIDでマッチ計算＋理由生成（/match/by-id-with-reason） ==========
# ※ エンドポイント実装は routers/matching.py に移動しました

# ルーターを登録（プレフィックスやタグは各ファイル内で定義）
app.include_router(job_postings_router)
app.include_router(matching_router)


# あると便利なヘルスチェック
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ローカル実行（python main.py）もできるようにしておくと便利
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )