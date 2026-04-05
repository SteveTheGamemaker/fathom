import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sodar.models.base import Base


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite session for tests."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client with isolated in-memory DB and full lifespan."""
    import sodar.database as db_module
    from sodar.app import create_app
    from httpx import ASGITransport, AsyncClient

    # Replace module-level engine/session with in-memory
    original_engine = db_module.engine
    original_session = db_module.async_session

    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    db_module.engine = test_engine
    db_module.async_session = test_session_factory

    app = create_app()

    # Run lifespan manually (creates tables + seeds data)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    await test_engine.dispose()
    db_module.engine = original_engine
    db_module.async_session = original_session
