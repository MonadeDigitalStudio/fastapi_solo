from typing import Type, TypeVar, overload
from sqlalchemy import ScalarResult, Select
from sqlalchemy.orm import Query
from sqlalchemy.ext.asyncio import (
    AsyncSession as SqlAlchemyAsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from fastapi import Depends, HTTPException

from ..utils.misc import log
from ..db.database import Base, select
from ..exc import DbException


class AsyncSessionFactory:
    sessionmaker: async_sessionmaker["AsyncSession"]

    @classmethod
    def new(cls, **kwargs):
        return cls.sessionmaker(**kwargs)

    @classmethod
    def init(
        cls,
        engine: AsyncEngine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        **kwargs
    ):
        """Initialize the database session factory

        params:
        - engine: the database engine

        **Example:**
        ```
        from sqlalchemy.ext.asyncio import create_async_engine
        from fastapi_solo.aio import AsyncSessionFactory

        engine = create_async_engine("sqlite+aiosqlite:///example.db")
        AsyncSessionFactory.init(engine)

        with AsyncSessionFactory.open() as db:
            ...
        ```
        """
        cls.sessionmaker = async_sessionmaker(
            bind=engine,
            autocommit=autocommit,
            autoflush=autoflush,
            expire_on_commit=expire_on_commit,
            class_=AsyncSession,
            **kwargs,
        )
        cls.engine = engine

    @classmethod
    def open(cls, **kwargs):
        return cls.new(**kwargs)


async def get_async_raw_session():
    """Get an injectable database session from request context"""
    log.debug("Getting db session")
    async with AsyncSessionFactory.open() as db:
        yield db
    log.debug("Db session closed")


T = TypeVar("T", bound=Base)


class AsyncSession(SqlAlchemyAsyncSession):
    """Database session with some extra methods"""

    @overload
    async def exec(self, q: "Select[T]") -> ScalarResult[T]: ...

    @overload
    async def exec(self, q): ...

    async def exec(self, q, **kwargs):
        result = await super().execute(q, **kwargs)
        if isinstance(q, (Select, Query)):
            return result.scalars()
        return result

    async def find_or_create(
        self, model: Type[Base], find_by=None, flush=True, **kwargs
    ):
        q = select(model)
        filters = kwargs
        if find_by:
            filters = {k: v for k, v in kwargs.items() if k in find_by}
        else:
            pks = list(map(lambda x: x.name, model.__mapper__.primary_key))
            if all(k in kwargs for k in pks):
                filters = {k: v for k, v in kwargs.items() if k in pks}

        q = q.filter_by(**filters)

        ret = (await self.exec(q)).one_or_none()
        if not ret:
            ret = model(**kwargs)
            self.add(ret)
            if flush:
                await self.flush()
        return ret

    async def upsert(self, model: Type[Base], find_by=None, flush=True, **kwargs):
        if not find_by:
            pks = list(map(lambda x: x.name, model.__mapper__.primary_key))
            if not all(k in kwargs for k in pks):
                raise DbException("find_by or primary key must be provided")
        e = await self.find_or_create(model, find_by=find_by, flush=False, **kwargs)
        for k, v in kwargs.items():
            setattr(e, k, v)
        if flush:
            await self.flush()
        return e


# transactions


class AsyncTransaction:
    _allow_nesting_root_router_transaction = False  # set to True to allow nesting the router root transaction, useful for testing

    def __init__(self, session: AsyncSession, nested=False):
        self.db = session
        self.nested = nested
        self._force_rollback = False

    async def __aenter__(self):
        await self._begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.tx or not self.tx.is_active:
            log.warning(
                "Transaction closed manually!!! "
                "Use t.force_commit() or t.force_rollback() from the current Transaction instance if you really need it instead"
            )
            return False
        if self._force_rollback or exc_type is not None:
            log.debug("Rolling back transaction")
            await self.tx.rollback()
            return False
        log.debug("Committing transaction")
        await self.tx.commit()
        return True

    async def _begin(self):
        if self.db.in_transaction():
            trs = self.db.get_transaction()
            if self.nested:
                log.debug("Starting nested transaction")
                self.tx = await self.db.begin_nested()
            elif trs and not trs.nested:
                log.debug("Using current transaction")
                self.tx = trs
            else:
                raise HTTPException(
                    500,
                    detail="Nested transaction not allowed. Use nested=True to force nesting",
                )
        else:
            log.debug("Starting new transaction")
            self.tx = await self.db.begin()

    async def force_commit(self):
        await self.tx.commit()
        await self._begin()

    async def force_rollback(self):
        await self.tx.rollback()
        await self._begin()

    def set_force_rollback(self):
        self._force_rollback = True


async def get_async_root_transaction(db: AsyncSession = Depends(get_async_raw_session)):
    """Get the root transaction from request context"""
    async with AsyncTransaction(
        db, AsyncTransaction._allow_nesting_root_router_transaction
    ) as tx:
        yield tx


async def get_async_db(tx: AsyncTransaction = Depends(get_async_root_transaction)):
    """Get an injectable transactional database session from request context"""
    return tx.db
