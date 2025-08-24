# ------------------------------------------------------------
# DB接続の土台。engine / SessionLocal / Base / get_db を定義。
# .env が URL直書きの場合は DATABASE_URL を優先。
# それ以外は DB_USER などの分割値から MySQL 用 URL を自動生成。
# どちらも無ければ SQLite にフォールバック。
# ------------------------------------------------------------
import os
from typing import Generator
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# .env を読み込む
try:
    from dotenv import load_dotenv  # 任意
    # backend/app/.env を最優先で読む（起動ディレクトリに依存しないように）
    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
    else:
        load_dotenv()
except Exception:
    pass

# ============================================================
# 1) 環境変数の読み込み
#    - まず DATABASE_URL（URL直書き）があればそれを使う
#    - 無ければ DB_USER 等の分割値から組み立てる
#    - どちらも無ければ SQLite にフォールバック
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 分割値（.env 推奨）
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST") or "localhost"
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME")
    # Azure で CA 証明書パスを指定する場合（任意）
    DB_SSL_CA = os.getenv("DB_SSL_CA")  # C:\Users\owner\STEP4\oneview\DigiCertGlobalRootCA.crt (3).pem

    if DB_USER and DB_PASSWORD and DB_HOST and DB_NAME:
        # パスワードなどに記号がある場合に備えてエンコード
        user = quote_plus(DB_USER)
        pwd = quote_plus(DB_PASSWORD)
        host = DB_HOST
        port = DB_PORT
        name = DB_NAME

        # 文字コードは utf8mb4 推奨
        DATABASE_URL = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4"
    else:
        # どちらも無ければローカル SQLite に退避（開発用）
        DATABASE_URL = "sqlite:///./app.db"

# （任意）本番で SQLite を絶対に使いたくない場合は .env に DISABLE_SQLITE=1 を設定
if os.getenv("DISABLE_SQLITE") == "1" and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite フォールバックが抑止されました。Azure MySQL の接続情報（DATABASE_URL または DB_*）を設定してください。"
    )

# ============================================================
# 2) create_engine（DBごとに微調整）
#    - SQLite は connect_args が必要
#    - MySQL/Azure は SSL を有効化（Azureは基本必須）
# ============================================================
def _is_mysql(url: str) -> bool:
    try:
        return url.split(":", 1)[0].startswith("mysql")
    except Exception:
        return False

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
        future=True,
    )
else:
    # MySQL / Postgres など
    if _is_mysql(DATABASE_URL):
        # --- SSLContext を明示的に作成して渡す（推奨） ---
        import ssl
        ctx = None
        DB_SSL_CA = os.getenv("DB_SSL_CA")
        if DB_SSL_CA and Path(DB_SSL_CA).exists():
            # CA を指定して検証を有効化
            ctx = ssl.create_default_context(cafile=str(Path(DB_SSL_CA).resolve()))
        else:
            # CA 未指定でも TLS を使う（Azure は TLS 必須）
            ctx = ssl.create_default_context()
        connect_args = {"ssl": ctx}
    else:
        # MySQL 以外（例：PostgreSQL）は connect_args を渡さない
        connect_args = {}

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # 接続死活監視（MySQL/Postgresで推奨）
        pool_recycle=1800,    # 長時間アイドルで切られる対策（秒）
        echo=False,           # SQLログを見たいときは True
        future=True,
        connect_args=connect_args,
    )

# ============================================================
# 3) セッションファクトリ / Base
# ============================================================
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)
Base = declarative_base()

# ============================================================
# 4) FastAPI で使う DB セッション依存関係
# ============================================================
def get_db() -> Generator:
    """
    FastAPI の Depends で使うDBセッション。
    使用後は必ず close() される。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()