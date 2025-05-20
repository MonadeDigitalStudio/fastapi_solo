from typing import (
    Any,
    Callable,
    List,
    Optional,
    overload,
    TYPE_CHECKING,
)
from typing_extensions import Self
from sqlalchemy import desc, func
from sqlalchemy.orm import (
    joinedload,
    selectinload,
)
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.properties import ColumnProperty
from fastapi import HTTPException
from datetime import datetime, date
from inflection import underscore

from ..utils.misc import parse_bool, log
from ..utils.config import FastapiSoloConfig
from ..utils.db import get_single_pk


class Queryable:
    """Mixin to make a model queryable"""

    model: Any

    def find(
        self,
        include: Optional[List[str]] = None,
        query_by: Optional[dict] = None,
        sort: Optional[List[str]] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> Self:
        """Create a query to find all the models

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

        query = select(Post).find(
            query_by={"title": "Hello", "message_text": "world"},
            sort="-message_text",
            page=1,
            size=10,
            include=["messages.tags"],
        )
        ```
        """
        q = self
        q = q.includes(*(include or []))
        q = q.query_by(**(query_by or {}))
        q = q.sort(*(sort or []))
        q = q.paginate(page, size)
        return q

    def query_by(self, **filters) -> Self:
        """Apply filters to the query

        you can filter all the custom scopes starting by of_ defined on the model

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

        query = select(Post).query_by(title="Hello", message_text="world")
        ```
        """
        if not hasattr(self.model, "__queryable__"):
            return self
        q = self
        if filters:
            for key, value in filters.items():
                if "[" in key and key.endswith("]"):
                    col = key.split("[")[0]
                    json_key = key.split("[", 1)[1].removesuffix("]")
                    q = self._apply_json_filter(q, col, json_key, value)
                    continue
                of_key = f"of_{key}"
                attr = self._get_model_attr(self.model, of_key)
                if attr and callable(attr):
                    q = attr(q, value)
                elif key in self.model.__queryable__:
                    attr = self._get_model_attr(self.model, key)
                    attr_type = getattr(attr, "property", None)
                    if attr and attr_type and isinstance(attr_type, ColumnProperty):
                        q = self._apply_column_filter(q, value, attr)

        return q  # type: ignore

    def sort(self, *sort: str) -> Self:
        """Apply sort to the query

        you can sort by all the custom scopes starting by by_ defined on the model and all the columns of the model by their name

        starts with "-" to sort descending

        **Example:**
        ```
        @queryable
        class Post(Base):
            __tablename__ = "posts"
            id = Column(Integer, primary_key=True)
            title = Column(String)
            messages = relationship("Message")

            @staticmethod
            def by_message_text(q, is_desc):
                field = desc(Message.text) if is_desc else Message.text
                return q.join(Post.messages).order_by(field)

        query = select(Post).sort("title")
        query = select(Post).sort("-message_text")
        ```
        """
        q = self
        for s in sort:
            q = q._sort(s)
        return q

    def _sort(self, sort: str):
        q: Any = self
        if sort:
            is_desc = sort[0] == "-"
            sort = sort[1:] if is_desc else sort
            if "[" in sort and sort.endswith("]"):
                col = sort.split("[")[0]
                json_key = sort.split("[", 1)[1].removesuffix("]")
                attr = self._get_model_attr(self.model, f"by_{col}")
                if attr and callable(attr):
                    q = attr(q, json_key, is_desc)
                return q
            attr = self._get_model_attr(self.model, f"by_{sort}")
            if attr and callable(attr):
                q = attr(q, is_desc)
            else:
                attr = self._get_model_attr(self.model, sort)
                if attr:
                    if is_desc:
                        attr = desc(attr)
                    q = q.order_by(attr)

        return q

    def includes(self, *include: str) -> Self:
        """Include relationships to the query

        you can include all the relationships of the model and the nested relationships by using the dot notation

        you can also include all the columns of the model by using "*" BUT IT IS NOT RECOMMENDED FOR PERFORMANCE REASONS

        **Example:**
        ```
        class Post(Base):
            __tablename__ = "posts"
            id = Column(Integer, primary_key=True)
            title = Column(String)
            messages = relationship("Message")


        class Message(Base):
            __tablename__ = "messages"
            id = Column(Integer, primary_key=True)
            text = Column(String)
            post_id = Column(Integer, ForeignKey("posts.id"))

            tags = relationship("Tag")
            attachments = relationship("Attachment")

        query = select(Post).includes("message.tags", "message.attachments")
        """
        q: Any = self
        if "*" in include:
            return q.options(selectinload("*"))
        for rel in include:
            rels = rel.split(".")
            join = self._join(self.model, rels)
            if join:
                q = q.options(join)
        return q

    def paginate(self, page: Optional[int], size: int | str | None = None) -> Self:
        """Paginate the query, apply the offset and limit to the query"""
        q: Any = self
        if page is not None and size is not None and size != "all":
            skip = (page - 1) * size
            q = q.offset(skip).limit(size)
        return q

    def find_id(self, id: Any, include: Optional[List[str]] = None):
        """Find a model by id

        params:
        - id: the id of the model
        - include: a list of relationships to include
        """
        q: Any = self.includes(*include or [])
        pk = get_single_pk(self.model)

        return q.where(pk == id)

    def _join(self, parent, rels, join=None, silent=False):
        attr = self._get_model_attr(parent, rels[0])
        attr_type = getattr(attr, "property", None)
        if attr and attr_type and isinstance(attr_type, RelationshipProperty):
            join = self._apply_join(join, attr, attr_type)
            if len(rels) > 1:
                join = self._join(attr.mapper.class_, rels[1:], join)
        elif not silent:
            raise HTTPException(422, f"Invalid relationship {rels[0]}")
        return join

    def _apply_join(self, join, attr, attr_type):
        if attr_type.uselist:
            join_fn = join.selectinload if join else selectinload
        else:
            join_fn = join.joinedload if join else joinedload
        return join_fn(attr)

    def _apply_column_filter(self, q, value, attr):
        try:
            if attr.type.python_type == bool:
                q = q.filter(attr == parse_bool(value))
            elif attr.type.python_type == int:
                q = q.filter(attr == int(value))
            elif attr.type.python_type == float:
                q = q.filter(attr == float(value))
            elif attr.type.python_type == str and FastapiSoloConfig.queryable_use_like:
                q = q.filter(attr.icontains(value))
            elif attr.type.python_type == datetime or attr.type.python_type == date:
                if isinstance(value, str) and "," in value:
                    x, y = value.split(",")
                    q = q.filter(func.date(attr).between(x.strip(), y.strip()))
                elif isinstance(value, list):
                    x, y = value
                    q = q.filter(func.date(attr).between(x, y))
                else:
                    q = q.filter(func.date(attr) == value)
            else:
                q = q.filter(attr == value)
        except Exception:
            log.warning(f"Invalid filter value {value} for {attr} - skipping filter")
        return q

    def _get_model_attr_k(self, model, key: str):
        attr = getattr(model, key, None)
        if not attr and model.__mapper__.polymorphic_map:
            for mapper in model.__mapper__.polymorphic_map.values():
                attr = getattr(mapper.class_, key, None)
                if attr:
                    break
        return attr

    def _get_model_attr(self, model, key: str):
        attr = self._get_model_attr_k(model, key)
        if not attr:
            attr = self._get_model_attr_k(model, underscore(key))
        return attr

    def _apply_json_filter(self, q, key, json_key, value):
        of_key = f"of_{key}"
        attr = self._get_model_attr(self.model, of_key)
        if attr and callable(attr):
            q = attr(q, json_key, value)
        return q


def _set_queryables(cls, filter_by):
    if filter_by == "*":
        filter_by = list(map(lambda x: x.name, cls.__mapper__.c))
    current = getattr(cls, "__queryable__", [])
    cls.__queryable__ = current + filter_by


@overload
def queryable(
    *filter_by: str,
): ...


@overload
def queryable(cls: Callable): ...


def queryable(cls: Callable | str, *args):
    """Decorator to make a model queryable from a route

    It will allow to filter and sort the model by the provided fields
    of_ and by_ scopes are allowed by default

    use * to allow all the fields

    **Example:**
    ```
    @queryable("name", "age")
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        name = Column(String)
        age = Column(Integer)

    query = select(User).query_by(name="Albert", age=42)
    ```
    """
    if callable(cls):
        _set_queryables(cls, "*")
        return cls

    if cls == "*":
        filter_by = "*"
    elif cls is None:
        filter_by = args
    else:
        filter_by = [cls, *args]

    def decorator(klass):
        _set_queryables(klass, filter_by)
        return klass

    return decorator
