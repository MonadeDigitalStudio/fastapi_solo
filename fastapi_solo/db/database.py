from typing import (
    Dict,
    Any,
    List,
    Type,
    Optional,
    TypeVar,
    overload,
    TYPE_CHECKING,
)
from uuid import UUID
from typing_extensions import deprecated
from sqlalchemy import ScalarResult, func, Engine, Select
from sqlalchemy.orm import (
    declarative_base as sqla_declarative_base,
    sessionmaker,
    Query,
    object_session,
    Session as SqlAlchemySession,
    Mapped,
)

from sqlalchemy.orm.relationships import RelationshipProperty
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from contextlib import contextmanager
from datetime import datetime

from .queryable import Queryable
from ..utils.misc import log
from ..utils.db import (
    get_single_pk,
    CreatedAtColumn,
    UpdatedAtColumn,
)
from ..exc import DbException


class SessionFactory:
    sessionmaker: Any = None

    @classmethod
    def new(cls, **kwargs) -> "Session":
        return cls.sessionmaker(**kwargs)

    @classmethod
    def init(cls, engine: Engine, autocommit=False, autoflush=False, **kwargs):
        """Initialize the database session factory

        params:
        - engine: the database engine

        **Example:**
        ```
        from sqlalchemy import create_engine
        from fastapi_solo import SessionFactory

        engine = create_engine("sqlite:///example.db")
        SessionFactory.init(engine)

        with SessionFactory.open() as db:
            ...
        ```
        """
        cls.sessionmaker = sessionmaker(
            bind=engine,
            autocommit=autocommit,
            autoflush=autoflush,
            class_=Session,
            query_cls=QueryModel,
            **kwargs,
        )
        cls.engine = engine

    @classmethod
    @contextmanager
    def open(cls, **kwargs):
        session = cls.new(**kwargs)
        try:
            yield session
        finally:
            session.close()


class _Base:

    def save(
        self,
        db: Optional[SqlAlchemySession] = None,
        update: BaseModel | Dict | Any = None,
        flush=True,
    ):
        """Save the model to the database

        params:
        - db: the database session, if not provided, it will be tried to get it from the model
        - update: an optional dict or a pydantic Model to update the model fields before saving
        - flush: if True, will flush the session to the database

        **Example:**
        ```
        user = User(name="Albert").save(db)
        # INSERT INTO users ...

        user.save(update={"name": "Albert Einstein"})
        # UPDATE users ...
        ```

        """
        if not db:
            db = object_session(self)
            assert db
        if update:
            if not isinstance(update, dict):
                update = update.model_dump(exclude_unset=True, exclude_defaults=True)
            for key, value in update.items():  # type: ignore
                value = _decode_field(self.__class__, db, key, value)
                setattr(self, key, value)
        db.add(self)
        if flush:
            db.flush()
        return self

    def delete(self, flush=True):
        """Delete the model from the database"""
        db = object_session(self)
        assert db
        db.delete(self)
        if flush:
            db.flush()

    @classmethod
    def create(
        cls,
        db: SqlAlchemySession,
        _obj: BaseModel | Dict | None = None,
        flush=True,
        **kwargs,
    ):
        """Create a new model instance and save it to the database"""
        obj = kwargs
        if _obj:
            obj = _obj
            if not isinstance(obj, dict):
                obj = obj.model_dump(exclude_unset=True, exclude_defaults=True)
        obj = {
            k: _decode_field(cls, db, k, v) for k, v in obj.items() if hasattr(cls, k)
        }
        model = cls(**obj)
        model.save(db, flush=flush)
        return model

    @classmethod
    def get_model(cls, model: str) -> Type["Base"]:
        models = cls.registry._class_registry.values()  # type: ignore
        for m in models:
            if hasattr(m, "__name__") and m.__name__ == model:
                return m
        raise DbException(f"Model {model} not found")


def declarative_base(**kwargs) -> Any:
    """Create a new declarative base class for the models

    **Example:**
    ```
    from fastapi_solo import declarative_base

    Base = declarative_base()
    ```

    """

    return sqla_declarative_base(cls=_Base, **kwargs)


class Base(declarative_base()):
    """Base class for all the models"""

    __abstract__ = True


if TYPE_CHECKING:

    Base = type("Base", (Base, _Base), {})


class BaseWithTS(Base):
    """Base class for all the models with timestamps"""

    __abstract__ = True
    created_at: Mapped[datetime] = CreatedAtColumn
    updated_at: Mapped[datetime] = UpdatedAtColumn


def _decode_field(cls, db, key, value):
    if (
        isinstance(value, list)
        and len(value) > 0
        and (isinstance(value[0], int) or isinstance(value[0], str) or isinstance(value[0], UUID))
    ):
        attr = getattr(cls, key)
        attr_type = getattr(attr, "property", None)
        if attr_type and isinstance(attr_type, RelationshipProperty):
            # many to many relationship
            rel_model = attr_type.mapper.class_
            if len(value) > 0:
                pk = get_single_pk(rel_model)
                rel_list = db.exec(select(rel_model).filter(pk.in_(value))).all()
                if len(rel_list) != len(value):
                    raise HTTPException(
                        400,
                        detail=f"Invalid {key} value. Invalid relationships",
                    )
                value = rel_list
    return value


def get_raw_session():
    """Get an injectable database session from request context"""
    log.debug("Getting db session")
    with SessionFactory.open() as db:
        yield db
    log.debug("Db session closed")


T = TypeVar("T", bound=Base)


class Session(SqlAlchemySession):
    """Database session with some extra methods"""

    @deprecated("Legacy method, use session.exec(...) instead")
    def query(self, *entities: Any, **kwargs: Any) -> "QueryModel":
        return super().query(*entities, **kwargs)  # type: ignore

    @overload
    def exec(self, q: "Select[T]") -> ScalarResult[T]: ...

    @overload
    def exec(self, q): ...

    def exec(self, q, **kwargs):
        if isinstance(q, Query):
            return q
        result = super().execute(q, **kwargs)
        if isinstance(q, Select):
            return result.scalars()
        return result

    def find_or_create(self, _model: Type[Base], find_by=None, flush=True, **kwargs):
        """Find or create a model

        it doesnt update the model if it already exists

        params:
        - find_by: a list of fields to find the model by, if not provided, it will be tried to find the model by all the fields
        - flush: if True, will flush the session to the database
        - kwargs: the fields to eventually create the model

        **Example:**
        ```
        user = User.find_or_create(name="Albert")

        user = User.find_or_create(find_by=["name"], name="Albert")
        ```
        """
        q = select(_model)
        filters = kwargs
        if find_by:
            filters = {k: v for k, v in kwargs.items() if k in find_by}
        else:
            pks = list(map(lambda x: x.name, _model.__mapper__.primary_key))
            if all(k in kwargs for k in pks):
                filters = {k: v for k, v in kwargs.items() if k in pks}

        q = q.filter_by(**filters)

        ret = self.exec(q).one_or_none()
        if not ret:
            ret = _model(**kwargs)
            self.add(ret)
            if flush:
                self.flush()
        return ret

    def upsert(self, _model: Type[Base], find_by=None, flush=True, **kwargs):
        """Update or create a model

        it will update the model if it already exists before returning it

        params:
        - find_by: a list of fields to find the model by, if not provided,
            it will be tried to find the model by primary key that should be provided in kwargs
        - flush: if True, will flush the session to the database
        - kwargs: the fields to upsert the model

        **Example:**
        ```
        user = User.upsert(id=4, name="Albert")

        user = User.upsert(find_by=["name"], name="Albert", age=42)
        ```
        """
        if not find_by:
            pks = list(map(lambda x: x.name, _model.__mapper__.primary_key))
            if not all(k in kwargs for k in pks):
                raise DbException("find_by or primary key must be provided")
        e = self.find_or_create(_model, find_by=find_by, flush=False, **kwargs)
        for k, v in kwargs.items():
            setattr(e, k, v)
        if flush:
            self.flush()
        return e


# transactions


class Transaction:
    """transaction handler for the database session

    params:
    - session: the database session
    - nested: if False use the current transaction if there is one instread of nesting a new one

    **Example:**
    ```
    with Transaction(db):
        insert...

    # at the end of the with block, the session will be committed if no exception is raised or rolled back if an exception is raised
    ```
    """

    _allow_nesting_root_router_transaction = False  # set to True to allow nesting the router root transaction, useful for testing

    def __init__(self, session: Session, nested=False):
        self.db = session
        self.nested = nested
        self._force_rollback = False

    def __enter__(self):
        self._begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.tx or not self.tx.is_active:
            log.warning(
                "Transaction closed manually!!! "
                "Use t.force_commit() or t.force_rollback() from the current Transaction instance if you really need it instead"
            )
            return False
        if self._force_rollback or exc_type is not None:
            log.debug("Rolling back transaction")
            self.tx.rollback()
            return False
        log.debug("Committing transaction")
        self.tx.commit()
        return True

    def _begin(self):
        if self.db.in_transaction():
            if self.nested:
                log.debug("Starting nested transaction")
                self.tx = self.db.begin_nested()
            elif self.db._transaction and not self.db._transaction.nested:
                log.debug("Using current transaction")
                self.tx = self.db._transaction
            else:
                raise HTTPException(
                    500,
                    detail="Nested transaction not allowed. Use nested=True to force nesting",
                )
        else:
            log.debug("Starting new transaction")
            self.tx = self.db.begin()

    def force_commit(self):
        self.tx.commit()
        self._begin()

    def force_rollback(self):
        self.tx.rollback()
        self._begin()

    def set_force_rollback(self):
        self._force_rollback = True


def get_root_transaction(db: Session = Depends(get_raw_session)):
    """Get the root transaction from request context"""
    with Transaction(db, Transaction._allow_nesting_root_router_transaction) as tx:
        yield tx


def get_db(tx: Transaction = Depends(get_root_transaction)):
    """Get an injectable transactional database session from request context"""
    return tx.db


# Query models


def _get_main_model_from_entities(entities):
    model = entities
    if hasattr(model, "__iter__"):
        model = model[0]
    if hasattr(model, "class_"):
        model = model.class_
    return model


class SelectModel(Select[T], Queryable):
    inherit_cache = True

    def __init__(self, *entities: T | Any, **kwargs):
        self.model = _get_main_model_from_entities(entities)
        super().__init__(*entities, **kwargs)

    def count(self) -> "SelectModel[Any]":
        return select(func.count()).select_from(self.subquery())


def select(*entities: Type[T] | Any) -> SelectModel[T]:
    return SelectModel(*entities)


class QueryModel(Query, Queryable):
    session: Session

    def __init__(
        self,
        entities: List[Base] | Base = [],
        session: Optional[Session] = None,
        *kargs,
        **kwargs,
    ):
        self.model = _get_main_model_from_entities(entities)
        super().__init__(entities, session=session, *kargs, **kwargs)

    def find_all(
        self,
        query_by: Optional[dict] = None,
        sort: Optional[List[str]] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> List[Base]:
        """Find all the models

        params:
        - query_by: a dict of filters to apply
            - you can filter all the columns of the model by their name and all the custom scopes starting by of_ defined on the model
            - by default, the filters are applied with the equality operator, you can override them with of_ scopes
        - sort: a string to sort the results
            - you can sort by all the columns of the model by their name and all the custom scopes starting by by_ defined on the model
            - starts with "-" to sort descending
        - page: the page number to paginate the results
        - size: the page size to paginate the results
        - include: a list of relationships to include
            - you can include all the relationships of the model and the nested relationships by using the dot notation

        **Example:**
        ```
        @queryable
        class Post(Base):
            __tablename__ = "posts"
            id = Column(Integer, primary_key=True)
            title = Column(String)
            messages = relationship("Message")

            @staticmethod
            def of_message_text(q, value):
                return q.join(Post.messages).filter(Message.text.contains(value))

            @staticmethod
            def by_message_text(q, is_desc):
                field = desc(Message.text) if is_desc else Message.text
                return q.join(Post.messages).order_by(field)

        posts = db.query(Post).find_all(
            query_by={"title": "Hello", "message_text": "world"},
            sort="-message_text",
            page=1,
            size=10,
            include=["messages.tags"],
        )
        ```
        """
        q = self.find(
            include=include,
            query_by=query_by,
            sort=sort,
            page=page,
            size=size,
        )
        return q.all()

    def find_id(self, id: Any, include: Optional[List[str]] = None) -> Base:
        """Find a model by id

        params:
        - id: the id of the model
        - include: a list of relationships to include
        """
        return super().find_id(id, include).one_or_none()

    def find_or_create(self, find_by=None, flush=True, **kwargs):
        return self.session.find_or_create(
            self.model, find_by=find_by, flush=flush, **kwargs
        )

    def upsert(self, find_by=None, flush=True, **kwargs):
        return self.session.upsert(self.model, find_by=find_by, flush=flush, **kwargs)
