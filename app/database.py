import sys
from sqlalchemy import create_engine, text
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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_sqlite_columns(target_engine) -> None:
    """Idempotently backfills new ownership columns on existing local SQLite databases."""
    if not str(target_engine.url).startswith("sqlite"):
        return
    migrations = [
        ("datasets", "owner_id", "VARCHAR NOT NULL DEFAULT 'analyst-1'"),
        ("analysis_runs", "created_by", "VARCHAR NOT NULL DEFAULT 'analyst-1'"),
        ("reports", "owner_id", "VARCHAR NOT NULL DEFAULT 'analyst-1'"),
    ]
    with target_engine.begin() as conn:
        for table, column, ddl in migrations:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db():
    from app.database import Base as TargetBase, engine as TargetEngine
    import app.models  # noqa: F401
    TargetBase.metadata.create_all(bind=TargetEngine)
    _ensure_sqlite_columns(TargetEngine)
    print(f"Database initialized with tables: {list(TargetBase.metadata.tables.keys())}")


if __name__ == "__main__":
    init_db()
