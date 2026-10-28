import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

settings = get_settings()

# For SQLite, check_same_thread=False is needed for multi-threaded FastAPI execution
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.database import Base as TargetBase, engine as TargetEngine
    import app.models  # noqa: F401
    TargetBase.metadata.create_all(bind=TargetEngine)
    print(f"Database initialized with tables: {list(TargetBase.metadata.tables.keys())}")


if __name__ == "__main__":
    init_db()
