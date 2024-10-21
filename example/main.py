from fastapi import FastAPI
from fastapi_solo import SessionFactory, Base
from fastapi_solo.aio import AsyncSessionFactory
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from example.api.main import router

engine = create_engine("sqlite:///example.db", echo=True)
Base.metadata.create_all(engine)
SessionFactory.init(engine)

engine2 = create_async_engine("sqlite+aiosqlite:///example.db", echo=True)
AsyncSessionFactory.init(engine2)

app = FastAPI(
    docs_url="/swagger",
    redoc_url="/redoc",
)

app.include_router(router, prefix="/api")
