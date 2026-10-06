# core/db.py
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@postgres-service:5432/cleaning_robot",
    pool_size=10,
    max_overflow=5,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session