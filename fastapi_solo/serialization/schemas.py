from fastapi import Depends, Request, Query
from pydantic import BaseModel, ConfigDict, BeforeValidator, Field, PlainSerializer
from fastapi.encoders import jsonable_encoder
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    List,
    Dict,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
    overload,
)
from sqlalchemy import inspect
from sqlalchemy.ext.associationproxy import AssociationProxy
from inflection import camelize
from collections import namedtuple
from datetime import datetime

from ..utils.misc import RuntimeType
from ..utils.config import FastapiSoloConfig
from ..db.database import Base


@overload
def all_optional(
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
): ...


@overload
def all_optional(include: Type[BaseModel]): ...


def all_optional(
    include: list[str] | Type[BaseModel] | None = None,
    exclude: Optional[list[str]] = None,
):
    """Return a decorator to make all the model fields optional

    params:
    - include: whitelist of fields to make optional
    - exclude: blacklist of fields to make optional

    **Example:**
    ```
    @all_optional
    class Post(BaseModel):
        title: str
        content: str
    ```
    """

    if exclude is None:
        exclude = []

    def decorator(cls: Type[BaseModel]):
        type_hints = get_type_hints(cls)
        fields = cls.model_fields
        if include is None:
            fields = fields.items()
        else:
            fields = ((name, fields[name]) for name in include if name in fields)  # type: ignore
        for name, field in fields:
            if name in exclude or not field.is_required:
                continue
            field.default = None
            cls.__annotations__[name] = Optional[type_hints[name]]  # type: ignore
        cls.model_rebuild(force=True)
        return cls

    if isinstance(include, type):
        klass = include
        include = None
        return decorator(klass)

    return decorator


def tzdatetime_encoder(obj: datetime):
    iso = obj.isoformat(timespec="seconds")
    if not obj.tzinfo:
        iso += "Z"
    return iso


DateTime = Annotated[datetime, PlainSerializer(tzdatetime_encoder)]


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda x: camelize(x, False),
        populate_by_name=True,
        from_attributes=True,
        json_encoders={datetime: tzdatetime_encoder},
    )

    @classmethod
    def render_model(cls, result, lazy_first_level: bool = False):
        """Create an instance of this class or a list of instances of this class from a sqlalchemy model or a list of sqlalchemy models"""
        if hasattr(result, "__iter__"):
            return [cls.render_model(obj, lazy_first_level) for obj in result]
        if lazy_first_level:
            result = lazy_validator(result)
        return cls.model_validate(result)

    @classmethod
    def render_json(
        cls,
        result,
        exclude: Optional[dict] = None,
        include: Optional[dict] = None,
        lazy_first_level: bool = False,
    ):
        """Render a json from a sqlalchemy model or a list of sqlalchemy models"""
        json = jsonable_encoder(
            cls.render_model(result, lazy_first_level),
            exclude=exclude,
            include=include,
            exclude_unset=True,
            exclude_defaults=True,
        )
        return json


class PaginationMeta(BaseSchema):
    total: int
    page_size: int
    total_pages: int
    current_page: int
    next_page: Optional[int] = None
    previous_page: Optional[int] = None


if TYPE_CHECKING:
    from .schema_models import ResponseSchema

T = TypeVar("T", bound=Union[BaseModel, "ResponseSchema"])


class PaginatedResponse(BaseSchema, Generic[T]):
    """A standard paginated response schema"""

    data: List[T]
    meta: Optional[PaginationMeta] = None


class PaginationParams:
    """Pagination query parameters"""

    def __init__(
        self,
        size: int | Literal["all"] | None = Query(
            None,
            alias="page[size]",
            description="The number of items per page, you can set it to **all** to disable pagination",
        ),
        page: int = Query(1, alias="page[number]"),
    ):
        self.size = size or FastapiSoloConfig.pagination_size
        self.page = page


class IncludesParams(List[str]):
    """Includes query parameters"""

    def __init__(
        self,
        include: Optional[str] = Query(
            None,
            description="A comma separated list of relationships to include Ex: author.posts,comments",
        ),
    ):
        includes = list(map(lambda x: x.strip(), include.split(","))) if include else []
        super().__init__(includes)


class FiltersParams(Dict[str, Any]):
    """Filters query parameters"""

    def __init__(
        self,
        request: Request,
    ):
        if request:
            filters = {
                k[7:-1]: v
                for k, v in request.query_params.items()
                if k.startswith("filter[") and k[-1] == "]"
            }
        else:
            filters = {}
        super().__init__(filters)


class SortParams(List[str]):
    """Sort query parameters"""

    def __init__(self, sort: Optional[str] = Query(None)):
        sort_by: List[str] = (
            list(map(lambda x: x.strip(), sort.split(","))) if sort else []
        )
        super().__init__(sort_by)


class CommonQueryParams:
    """Common query parameters (filters, includes, sort)"""

    def __init__(
        self,
        filters: Annotated[dict, Depends(FiltersParams)],
        includes: Annotated[List[str], Depends(IncludesParams)],
        sort: Annotated[List[str], Depends(SortParams)],
    ):
        self.filters = filters or {}
        self.sort = sort or []
        self.includes = includes or []


# models relationships


def OpenStruct(**kwargs):
    return namedtuple("OpenStruct", kwargs.keys())(**kwargs)


def lazy_validator(value):
    if not isinstance(value, Base):
        return value
    inspector = inspect(value)
    model_unloaded = inspector.unloaded
    proxy_unloaded = {
        k
        for k, v in inspector.mapper.all_orm_descriptors.items()
        if isinstance(v, AssociationProxy) and v.target_collection in model_unloaded
    }
    unloaded = model_unloaded | proxy_unloaded

    d = {
        k: getattr(value, k)
        for k in dir(value)
        if not k.startswith("_")
        and k not in unloaded
        and not callable(getattr(type(value), k, None))
    }

    return OpenStruct(**d)


@RuntimeType
def Lazy(parameter):
    """A special form to declare a lazy relationship in a pydantic model
    **Example:**
    ```
    class Message(BaseSchema):
        ...

    class Post(BaseSchema):
        ...
        messages: Lazy[Message]
    ```
    """
    return Annotated[parameter, BeforeValidator(lazy_validator)]


@RuntimeType
def HasOne(parameter):
    """A special form to declare a has one relationship in a pydantic model
    **Example:**
    ```
    class Post(BaseSchema):
        ...

    class Message(BaseSchema):
        ...
        post: HasOne[Post]
    ```
    """
    return Annotated[
        Optional[Lazy[parameter]],
        Field(default=None),
    ]


@RuntimeType
def HasMany(parameter):
    """A special form to declare a has many relationship in a pydantic model
    **Example:**
    ```
    class Message(BaseSchema):
        ...

    class Post(BaseSchema):
        ...
        messages: HasMany[Message]
    ```
    """
    return Annotated[
        Optional[List[Lazy[parameter]]],
        Field(default=None),
    ]


def _get_query_params_for_model(model: Base):
    columns = model.__queryable__ if hasattr(model, "__queryable__") else []
    if columns == "*":
        columns = map(lambda x: x.name, model.__mapper__.c)
    scopes = filter(lambda x: x.startswith("of_"), dir(model))
    return reversed(
        [Query(None, alias=f"filter[{column}]") for column in columns]
        + [Query(None, alias=f"filter[{scope[3:]}]") for scope in scopes]
    )


def get_swagger_filters(*models: Base):
    """Return an injectable dependency to add the swagger documentation for all the filters available on the models"""
    query_params = []
    for model in models:
        if model.__mapper__.with_polymorphic:
            poly = model.__mapper__.polymorphic_map.values()
            for p in poly:
                query_params += _get_query_params_for_model(p.class_)
        else:
            query_params += _get_query_params_for_model(model)
    ret = None
    for q in query_params:
        if ret:
            ret = lambda _=q, __=Depends(ret): None  # noqa
        else:
            ret = lambda _=q: None  # noqa
    return ret
