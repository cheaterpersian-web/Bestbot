from contextlib import asynccontextmanager
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from models.base import Base


def _sanitize_db_url(url: str) -> str:
    if not url:
        return ""
    try:
        # Hide password part user:pass@
        prefix, rest = url.split("://", 1)
        if "@" in rest and ":" in rest.split("@", 1)[0]:
            creds, host_part = rest.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                rest = f"{user}:***@{host_part}"
        return f"{prefix}://{rest}"
    except Exception:
        return url

effective_url = os.getenv("DATABASE_URL", settings.database_url)
print(f"[db] Effective DATABASE_URL: {_sanitize_db_url(effective_url)}")

engine = create_async_engine(effective_url, echo=False, pool_pre_ping=True, pool_size=5, max_overflow=10)
AsyncSessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_db_session():
    session: AsyncSession = AsyncSessionMaker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

