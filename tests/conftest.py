import pytest
from typing import Any, Generator
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from fastapi_solo import Base, Session, SessionFactory, Transaction
from fastapi_solo.db.database import get_db
from tests.mock.router import api_router


@pytest.fixture(autouse=True, scope="session")
def create_db() -> Generator[Any, Any, None]:
    engine = create_engine(
        "sqlite:///test.db", connect_args={"check_same_thread": False}, echo=True
    )

    SessionFactory.init(engine)
    Transaction._allow_nesting_root_router_transaction = True
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # Create the tables.
    engine.connect()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    return app


@pytest.fixture()
def db() -> Generator[Session, Any, None]:
    session = SessionFactory.new()
    try:
        session.begin()
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(app: FastAPI, db) -> Generator[TestClient, Any, None]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
