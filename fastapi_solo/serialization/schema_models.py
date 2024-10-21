from pydantic import create_model
from typing import (
    List,
    Optional,
    Type,
    Union,
    Dict,
    Set,
    Tuple,
    Any,
    get_args,
    get_origin,
    get_type_hints,
)
from sqlalchemy.sql.elements import BinaryExpression
from hashlib import md5
from ..db.database import Base
from ..utils.db import get_single_pk

from .schemas import BaseSchema, HasMany, HasOne, Lazy

SymList = Dict[str, Any] | Set[str] | Tuple | List


def _flatten_sym_list(sym_list: Set[str] | Tuple[str] | List[str]) -> Dict[str, Any]:
    base = {}
    for k in sym_list:
        if isinstance(k, str):
            base[k] = True
        else:
            base.update(_normalize_sym_list(k))
    return base


def _normalize_sym_list(sym_list: SymList) -> Dict[str, Any]:
    if isinstance(sym_list, dict):
        for k, v in sym_list.items():
            if isinstance(v, (set, tuple, list, dict)):
                sym_list[k] = _normalize_sym_list(v)
    elif isinstance(sym_list, (set, tuple, list)):
        return _flatten_sym_list(sym_list)
    return sym_list


def _build_fields(fields, model, exclude, include, all_optional):
    for column in model.__mapper__.c:
        if column.name in exclude:
            continue
        if include and column.name not in include:
            continue
        if "password" in column.name and column.name not in (include or {}):
            continue
        type_ = column.type.python_type
        if all_optional or column.nullable or column.default:
            fields[column.name] = (Optional[type_], None)
        else:
            fields[column.name] = (type_, ...)


def _build_virtual_fields(fields, model, exclude, include):
    for prop in dir(model):
        if prop in exclude:
            continue
        if include and prop not in include:
            continue
        attr = getattr(model, prop)
        if isinstance(attr, (property, BinaryExpression)):
            if hasattr(attr, "type"):
                type_ = attr.type.python_type  # type: ignore
            else:
                type_ = get_type_hints(attr.fget).get("return", Any)
            fields[prop] = (Optional[type_], None)


def _build_relationship(
    rel_fields,
    model,
    rel_key,
    exclude,
    include,
    relationships,
    extras,
    all_optional,
    include_virtuals,
    use_dynamic_relationships,
):
    rel = model.__mapper__.relationships[rel_key]
    model_rel = rel.mapper.class_
    r = {}
    e = {}
    i = {}
    x = {}
    if exclude and isinstance(exclude, dict):
        e = exclude.get(rel_key, {})
    if include and isinstance(include, dict):
        i = include.get(rel_key, {})
    if isinstance(relationships, dict) and isinstance(
        relationships[rel_key], (dict, set, tuple, list)
    ):
        r = relationships[rel_key]
    if extras.get(rel_key) and isinstance(extras[rel_key], dict):
        x = extras[rel_key]
    schema_rel = _generate_schema(model_rel, e, i, r, x, all_optional, include_virtuals)
    if rel.uselist:
        R = (
            HasMany[schema_rel]  # type: ignore
            if use_dynamic_relationships
            else Optional[List[schema_rel]]
        )
        rel_fields[rel_key] = (R, None)
    else:
        R = (
            HasOne[schema_rel]  # type: ignore
            if use_dynamic_relationships
            else Optional[schema_rel]
        )
        rel_fields[rel_key] = (R, None)


def _custom_schema(
    model: Type[Base],
    exclude: dict = {},
    include: dict = {},
    relationships: dict = {},
    extras: Dict[str, Any] = {},
    all_optional: bool = True,
    include_virtuals: bool = True,
    name: Optional[str] = None,
    use_dynamic_relationships: bool = True,
    base_name: Optional[str] = None,
):
    name = name or _qs(
        model,
        exclude,
        include,
        relationships,
        extras,
        all_optional,
        include_virtuals,
        use_dynamic_relationships,
    )
    fields = {}
    rel_fields = {}
    _build_fields(fields, model, exclude, include, all_optional)

    if include_virtuals:
        _build_virtual_fields(fields, model, exclude, include)

    for rel_key in relationships:
        _build_relationship(
            rel_fields,
            model,
            rel_key,
            exclude,
            include,
            relationships,
            extras,
            all_optional,
            include_virtuals,
            use_dynamic_relationships,
        )

    extras = {
        k: (v, None if all_optional or _is_optional(v) else ...)
        for k, v in extras.items()
        if not isinstance(v, dict)
    }
    return create_model(
        base_name or name, __base__=BaseSchema, **fields, **rel_fields, **extras
    )


def _is_optional(field):
    return get_origin(field) is Union and type(None) in get_args(field)


def _qs(
    model: Type[Base],
    exclude: dict = {},
    include: dict = {},
    relationships: dict = {},
    extras: Dict[str, type | dict] = {},
    all_optional: bool = True,
    include_virtuals: bool = True,
    use_dynamic_relationships: bool = True,
):
    enc = ""
    if exclude:
        enc += f"-({_qs_dict(exclude)})"
    if include:
        enc += f"+({_qs_dict(include)})"
    if relationships:
        enc += f"&({_qs_dict(relationships)})"
    if extras:
        enc += f"!({_qs_dict(extras)})"
    if all_optional:
        enc += "?"
    if include_virtuals:
        enc += "*"
    if not use_dynamic_relationships:
        enc += "!"
    enc = md5(enc.encode()).hexdigest()[:8]
    return f"{model.__name__}${enc}"


def _qs_dict(e: SymList):
    a = []
    keys = sorted(e)
    for k in keys:
        if isinstance(e, dict) and isinstance(e[k], (dict, set, tuple, list)):
            a.append(f"{k}[{_qs_dict(e[k])}]")
        else:
            a.append(k)
    return ",".join(a)


__schema_cache = {}


def response_schema(
    model: Type[Base] | str,
    exclude: SymList = {},
    include: SymList = {},
    relationships: SymList = {},
    extras: Dict[str, type | dict] = {},
    all_optional: bool = True,
    include_virtuals: bool = True,
    use_dynamic_relationships: bool = True,
    lazy_first_level: bool = False,
) -> Any:
    """Return a schema for the given model

    params:
    - model: the model to create the schema for
    - exclude: a dictionary of fields to exclude from the schema (blacklist)
    - include: a dictionary of fields to include in the schema (whitelist)
    - relationships: a dictionary of relationships to include in the schema
    - extras: a dictionary of extra fields to add to the schema
    - all_optional: whether to make all the fields optional or follow the model definition
    - include_virtuals: whether to include virtual properties in the schema
    - use_dynamic_relationships: set to False to resolve all the lazy relationships in serialization
    - lazy_first_level: set to True lazy resolve relationships from the first level

    column names that contain "password" are excluded by default if not included explicitly

    **Example:**
    ```
    Post = response_schema(
        "Post",
        exclude={
            "messages": {
                "post_id": True,
                "text": True,
                "post": {
                    "messages": {
                        "tags": {"tag_id"},
                    }
                },
            }
        },
        relationships={
            "messages": {"post"},
        },
        extras={"messages": {"custom_field": str}},
    )
    ```
    """
    return _generic_schema(
        model,
        exclude,
        include,
        relationships,
        extras,
        all_optional,
        include_virtuals,
        use_dynamic_relationships,
        lazy_first_level,
    )


def _generic_schema(
    model: Type[Base] | str,
    exclude: SymList = {},
    include: SymList = {},
    relationships: SymList = {},
    extras: Dict[str, type | dict] = {},
    all_optional: bool = True,
    include_virtuals: bool = True,
    use_dynamic_relationships: bool = True,
    lazy_first_level: bool = False,
    base_name: Optional[str] = None,
):
    exclude = _normalize_sym_list(exclude)
    include = _normalize_sym_list(include)
    relationships = _normalize_sym_list(relationships)
    extras = _normalize_sym_list(extras)
    return _generate_schema(
        model,
        exclude,
        include,
        relationships,
        extras,
        all_optional,
        include_virtuals,
        use_dynamic_relationships,
        lazy_first_level,
        base_name,
    )


def _generate_schema(
    model: Type[Base] | str,
    exclude: dict = {},
    include: dict = {},
    relationships: dict = {},
    extras: Dict[str, type | dict] = {},
    all_optional: bool = True,
    include_virtuals: bool = True,
    use_dynamic_relationships: bool = True,
    lazy_first_level: bool = False,
    base_name: Optional[str] = None,
) -> Any:
    if include:
        relationships = {
            k: v for k, v in include.items() if isinstance(v, (dict, set, tuple, list))
        }
    if isinstance(model, str):
        model = Base.get_model(model)

    name = _qs(
        model,
        exclude,
        include,
        relationships,
        extras,
        all_optional,
        include_virtuals,
        use_dynamic_relationships,
    )
    schema = __schema_cache.get(name)
    if not schema:
        schema = _custom_schema(
            model=model,
            exclude=exclude,
            include=include,
            relationships=relationships,
            extras=extras,
            all_optional=all_optional,
            include_virtuals=include_virtuals,
            name=name,
            use_dynamic_relationships=use_dynamic_relationships,
            base_name=base_name,
        )
        __schema_cache[name] = schema

    if lazy_first_level:
        schema = Lazy[schema]  # type: ignore
    return schema


def request_schema(
    model: Base,
    all_optional: bool = False,
    exclude: SymList = {},
    include: SymList = {},
    relationships: SymList = {},
    extras: Dict[str, type | dict] = {},
) -> Any:
    """Return a schema for the given model excluding id and virtual fields"""
    if isinstance(model, str):
        model = Base.get_model(model)
    pk = get_single_pk(model).name
    if not isinstance(exclude, dict):
        exclude = {k: True for k in exclude}
    return _generic_schema(
        model,
        {pk: True, "created_at": True, "updated_at": True, **exclude},
        include,
        relationships,
        extras,
        all_optional,
        False,
        False,
    )


_EXCL_KEYS = {
    "model",
    "include",
    "exclude",
    "relationships",
    "extras",
    "all_optional",
    "include_virtuals",
    "use_dynamic_relationships",
    "lazy_first_level",
    "exclude_pk",
    "exclude_timestamps",
}


class _MetaSchema(type):
    def __new__(cls, name, bases, attrs):
        if bases:
            model = attrs.get("__model__", name)
            cls._fix_attrs(attrs)
            attrs = {**bases[0].__dict__, **attrs}
            if attrs["__exclude_pk__"]:
                if isinstance(model, str):
                    model = Base.get_model(model)
                pk = get_single_pk(model).name
                if not isinstance(attrs["__exclude__"], dict):
                    attrs["__exclude__"] = {k: True for k in attrs["__exclude__"]}
                attrs["__exclude__"] = {pk: True, **attrs["__exclude__"]}
            if attrs["__exclude_timestamps__"]:
                if not isinstance(attrs["__exclude__"], dict):
                    attrs["__exclude__"] = {k: True for k in attrs["__exclude__"]}
                attrs["__exclude__"] = {
                    "created_at": True,
                    "updated_at": True,
                    **attrs["__exclude__"],
                }

            return _generic_schema(
                model=model,
                include=attrs["__include__"],
                exclude=attrs["__exclude__"],
                relationships=attrs["__relationships__"],
                extras=attrs["__extras__"],
                all_optional=attrs["__all_optional__"],
                include_virtuals=attrs["__include_virtuals__"],
                use_dynamic_relationships=attrs["__use_dynamic_relationships__"],
                lazy_first_level=attrs["__lazy__"],
                base_name=name,
            )
        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def _fix_attrs(attrs):
        if attrs.get("__annotations__"):
            if not attrs.get("__extras__"):
                attrs["__extras__"] = {}
            attrs["__extras__"].update(
                {
                    k: v
                    for k, v in attrs["__annotations__"].items()
                    if k not in _EXCL_KEYS
                }
            )


class ResponseSchema(metaclass=_MetaSchema):
    """Base class for responses

    class variables:
    - __model__: the model to create the schema for
    - __exclude__: a dictionary of fields to exclude from the schema (blacklist)
    - __include__: a dictionary of fields to include in the schema (whitelist)
    - __relationships__: a dictionary of relationships to include in the schema
    - __extras__: a dictionary of extra fields to add to the schema
    - __all_optional__: whether to make all the fields optional or follow the model definition
    - __include_virtuals__: whether to include virtual properties in the schema
    - __use_dynamic_relationships__: set to False to resolve all the lazy relationships in serialization
    - __lazy__: set to True lazy resolve relationships from the first level
    - __exclude_pk__: set to True to exclude the primary key from the schema
    - __exclude_timestamps__: set to True to exclude the timestamps from the schema
    - **extras: extra fields to add to the schema

    **Example:**
    ```
    class Post(ResponseSchema):
        __model__ = "Post"
        __relationships__ = {
            "messages": {"tags"},
        }
        __extras__ = {"messages": {"extra_field": str}}

        extra_field_2: str
    ```
    """

    __model__: Type[Base] | str
    __relationships__: SymList = {}
    __include__: SymList = {}
    __exclude__: SymList = {}
    __extras__: Dict[str, type | dict] = {}
    __all_optional__: bool = True
    __include_virtuals__: bool = True
    __use_dynamic_relationships__: bool = True
    __lazy__: bool = True
    __exclude_pk__: bool = False
    __exclude_timestamps__ = False

    @classmethod
    def render_model(cls, result, lazy_first_level: bool = False): ...

    @classmethod
    def render_json(
        cls,
        result,
        exclude: Optional[SymList] = None,
        include: Optional[SymList] = None,
        lazy_first_level: bool = False,
    ): ...


class RequestSchema(metaclass=_MetaSchema):
    """Base class for requests

    **Example:**
    ```
    class PostUpdate(RequestSchema):
        __model__ = "Post"
        __all_optional__ = True
        __extras__ = {"messages": List[int]}
    ```
    """

    __model__: Type[Base] | str
    __include__: SymList = {}
    __exclude__: SymList = {}
    __extras__: Dict[str, type | dict] = {}
    __all_optional__: bool = False
    __exclude_pk__: bool = True
    __exclude_timestamps__ = True

    # private, use ResponseSchema instead if you need to customize this
    __relationships__: SymList = {}
    __include_virtuals__: bool = False
    __use_dynamic_relationships__: bool = False
    __lazy__: bool = False
