from __future__ import annotations

import os
import sys
from pathlib import Path

from logging.config import fileConfig
from sqlalchemy import create_engine
from sqlalchemy import pool
from alembic import context

# ===== 追加: SSL 用 =====
import ssl
try:
    import certifi  # 信頼できる CA バンドル（あると安定）
    _CA_FILE = certifi.where()
except Exception:
    _CA_FILE = None

# ============================================================
# 1) アプリへのパスを通す（backend/app を import 可能にする）
#    このファイルの場所: backend/alembic/env.py
#    → backend/app を sys.path に追加
# ============================================================
CURRENT_DIR = Path(__file__).resolve()          # .../backend/alembic/env.py
BACKEND_DIR = CURRENT_DIR.parents[1]            # .../backend
APP_DIR = BACKEND_DIR / "app"                   # .../backend/app
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# .env を読む（database.py が読む場合は省略可／冪等のためここでもロードOK）
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# ここからアプリの database を読み込む
# Base: モデルのメタデータ
# DATABASE_URL: 接続先（.env で定義したものが database.py で組み立てられる）
from database import Base, DATABASE_URL  # noqa: E402

# Alembic Config オブジェクト
config = context.config

# ログ設定（alembic.ini の設定を反映）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic が参照するメタデータ（自動マイグレーションで使用）
target_metadata = Base.metadata

# ============================================================
# 補助: Azure MySQL などの SSL 必須環境に対応した connect_args
# ============================================================
def _connect_args_for_url(url: str) -> dict:
    """MySQL(Azure)の場合に SSL を自動付与。その他は空。"""
    try:
        scheme = url.split(":", 1)[0]
    except Exception:
        scheme = ""
    if scheme.startswith("mysql"):
        # Azure Database for MySQL は基本 SSL 必須
        # ★ SSLContext を明示的に作成（certifi があればそれを利用）
        if _CA_FILE:
            ctx = ssl.create_default_context(cafile=_CA_FILE)
        else:
            ctx = ssl.create_default_context()
        return {"ssl": ctx}
    return {}

# ============================================================
# オフラインモード（接続せずに SQL を生成）
# ============================================================
def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,   # 型変更も検知
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

# ============================================================
# オンラインモード（DBに接続して適用）
# ============================================================
def run_migrations_online() -> None:
    url = DATABASE_URL
    connect_args = _connect_args_for_url(url)

    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,  # ← ここで SSL を有効化（Azure想定）
    )

    with engine.begin() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,           # 型変更も検知
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# ============================================================
# エントリーポイント
# ============================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()