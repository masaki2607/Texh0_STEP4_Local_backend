from __future__ import annotations
import os
import faiss
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from openai import OpenAI  

# ===============================
# 環境変数と初期化
# ===============================
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("環境変数 OPENAI_API_KEY が設定されていません。")

# OpenAIクライアントを作成
client = OpenAI(api_key=api_key)  

# SBERTモデル（多言語対応）
sbert = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 求人説明文（仮データ）※ 必要なら DB や job_postings から取得に変更可
job_descriptions = [
    "柔軟な働き方が可能なプロジェクトマネージャーの募集。Python経験歓迎。",
    "フルリモート可能なWebエンジニア募集。ReactやVue経験者歓迎。",
    "バックエンド開発者募集。FastAPI経験ある方優遇。リモートOK。"
]

# ベクトル化して FAISS に登録
job_embeddings = sbert.encode(job_descriptions)
dimension = job_embeddings[0].shape[0]
index = faiss.IndexFlatL2(dimension)
index.add(np.array(job_embeddings))

# ===============================
# マッチ理由生成（RAG + GPT）
# ===============================
def generate_match_reason(user_info: str) -> str:
    """
    求職者情報を SBERT + FAISS で求人とマッチングし、
    その結果を GPT で理由として自然文に変換。
    """
    try:
        # FAISS で最も近い求人を検索
        D, I = index.search(sbert.encode([user_info]), k=1)
        matched_description = job_descriptions[I[0][0]]

        # プロンプト作成
        prompt = f"""
あなたは人材紹介エージェントです。
以下の求職者情報と求人情報をもとに、なぜマッチしているかを日本語で自然に説明してください。

【求職者】
{user_info}

【求人情報】
{matched_description}

# マッチ理由（100文字程度）：
"""

        # GPT で自然文生成
        response = client.chat.completions.create(
            model="gpt-4",  # 必要に応じて gpt-3.5-turbo に変更可
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        # 失敗した場合はテンプレで返す
        return (
            "候補者の希望条件と求人要件を総合的に照合しました。"
            "スキル・勤務地・働き方の希望が概ね一致しています。"
            f"（候補者要約: {user_info[:180]}...）"
            f"※エラー: {str(e)}"
        )