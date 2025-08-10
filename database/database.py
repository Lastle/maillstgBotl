from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from .models import Base
from config import DATABASE_URL, SYNC_DATABASE_URL

# Создаем асинхронный движок PostgreSQL
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300
)

# Создаем асинхронную фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Синхронный движок для обратной совместимости
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

async def init_db():
    """Асинхронная инициализация базы данных"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def init_db_sync():
    """Синхронная инициализация базы данных (для обратной совместимости)"""
    Base.metadata.create_all(bind=sync_engine)

def get_db() -> Session:
    """Синхронное получение сессии базы данных (для обратной совместимости)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_async_db():
    """Асинхронное получение сессии базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_db_session() -> AsyncSession:
    """Получение асинхронной сессии базы данных"""
    return AsyncSessionLocal() 