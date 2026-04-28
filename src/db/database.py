"""数据库连接与会话管理"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from src.config import get_settings

settings = get_settings()

# ============== 异步引擎（主数据库） ==============
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


# ============== 同步引擎（SessionStore 降级用） ==============
_database_url = settings.database_url_sync or settings.database_url
sync_db_url = (
    _database_url
    .replace("postgresql+asyncpg", "postgresql")
    .replace("+asyncpg", "")
)

sync_engine = create_engine(
    sync_db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)


def get_sync_db():
    """获取同步数据库会话（用于 SessionStore 降级）"""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============== ORM Base ==============
class Base(DeclarativeBase):
    """SQLAlchemy模型基类"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await async_engine.dispose()
    sync_engine.dispose()


