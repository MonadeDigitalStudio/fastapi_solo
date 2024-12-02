import pytest
from typing import Any, AsyncGenerator, Generator
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi_solo import Base, Session, SessionFactory, Transaction
from fastapi_solo.aio import (
    AsyncSessionFactory,
    AsyncTransaction,
    AsyncSession,
    get_async_db,
)
from fastapi_solo.db.database import get_db
from tests.mock.router import api_router
from tests.mock.async_router import async_api_router
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True, scope="session")
def create_db() -> Generator[Any, Any, None]:
    engine = create_engine(
        "sqlite:///test.db", connect_args={"check_same_thread": False}, echo=True
    )
    async_engine = create_async_engine(
        "sqlite+aiosqlite:///test.db",
        connect_args={"check_same_thread": False},
        echo=True,
    )

    SessionFactory.init(engine)
    AsyncSessionFactory.init(async_engine)
    Transaction._allow_nesting_root_router_transaction = True
    AsyncTransaction._allow_nesting_root_router_transaction = True
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # Create the tables.
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    app.include_router(async_api_router)
    return app


@pytest.fixture()
def db() -> Generator[Session, Any, None]:
    session = SessionFactory.new()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest_asyncio.fixture()
async def async_db() -> AsyncGenerator[AsyncSession, Any]:
    async with AsyncSessionFactory.open() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture()
def client(app: FastAPI, db) -> Generator[TestClient, Any, None]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture()
async def async_client(app: FastAPI, async_db) -> AsyncGenerator[AsyncClient, Any]:
    app.dependency_overrides[get_async_db] = lambda: async_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
