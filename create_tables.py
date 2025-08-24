# モデルをすべてインポートして Base.metadata.create_all するだけ
from database import Base, engine
from models import *  # 全モデルを読み込む（__init__.py で集約推奨）

print("Creating tables in the database...")
Base.metadata.create_all(bind=engine)
print("Done.")