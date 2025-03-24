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
from ..utils.config import FastapiSoloConfig

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
    rel = model.__mapper__.relationships.get(rel_key)
    if not rel:
        return
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
    lazy_first_level: bool | None = None,
    auto_include_relationships: bool = False,
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
        auto_include_relationships=auto_include_relationships,
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
    lazy_first_level: bool | None = None,
    base_name: Optional[str] = None,
    auto_include_relationships: bool = False,
):
    exclude = _normalize_sym_list(exclude)
    include = _normalize_sym_list(include)
    relationships = _normalize_sym_list(relationships)
    extras = _normalize_sym_list(extras)
    if auto_include_relationships:
        if isinstance(model, str):
            model = Base.get_model(model)
        for rel in model.__mapper__.relationships.keys():  # type: ignore
            if rel not in relationships:
                relationships[rel] = True
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
    lazy_first_level: bool | None = None,
    base_name: Optional[str] = None,
) -> Any:
    if lazy_first_level is None:
        lazy_first_level = not FastapiSoloConfig.include_first_level_relationships
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
        schema = Lazy[schema]
    return schema


def request_schema(
    model: Type[Base],
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
            model = attrs.get("model", name)
            cls._fix_attrs(attrs)
            attrs = {**bases[0].__dict__, **attrs}
            if attrs["exclude_pk"]:
                if isinstance(model, str):
                    model = Base.get_model(model)
                pk = get_single_pk(model).name
                if not isinstance(attrs["exclude"], dict):
                    attrs["exclude"] = {k: True for k in attrs["exclude"]}
                attrs["exclude"] = {pk: True, **attrs["exclude"]}
            if attrs["exclude_timestamps"]:
                if not isinstance(attrs["exclude"], dict):
                    attrs["exclude"] = {k: True for k in attrs["exclude"]}
                attrs["exclude"] = {
                    "created_at": True,
                    "updated_at": True,
                    **attrs["exclude"],
                }

            return _generic_schema(
                model=model,
                include=attrs["include"],
                exclude=attrs["exclude"],
                relationships=attrs["relationships"],
                extras=attrs["extras"],
                all_optional=attrs["all_optional"],
                include_virtuals=attrs["include_virtuals"],
                use_dynamic_relationships=attrs["use_dynamic_relationships"],
                lazy_first_level=attrs["lazy"],
                base_name=name,
                auto_include_relationships=attrs.get(
                    "auto_include_relationships", False
                ),
            )
        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def _fix_attrs(attrs):
        if attrs.get("__annotations__"):
            if not attrs.get("extras"):
                attrs["extras"] = {}
            attrs["extras"].update(
                {
                    k: v
                    for k, v in attrs["__annotations__"].items()
                    if k not in _EXCL_KEYS
                }
            )


class ResponseSchema(metaclass=_MetaSchema):
    """Base class for responses

    class variables:
    - model: the model to create the schema for
    - exclude: a dictionary of fields to exclude from the schema (blacklist)
    - include: a dictionary of fields to include in the schema (whitelist)
    - relationships: a dictionary of relationships to include in the schema
    - extras: a dictionary of extra fields to add to the schema
    - all_optional: whether to make all the fields optional or follow the model definition
    - include_virtuals: whether to include virtual properties in the schema
    - use_dynamic_relationships: set to False to resolve all the lazy relationships in serialization
    - lazy: set to True lazy resolve relationships from the first level
    - exclude_pk: set to True to exclude the primary key from the schema
    - exclude_timestamps: set to True to exclude the timestamps from the schema
    - **kwargs: extra fields to add to the schema

    **Example:**
    ```
    class Post(ResponseSchema):
        model = "Post"
        relationships = {
            "messages": {"tags"},
        }
        extras = {"messages": {"extra_field": str}}

        extra_field_2: str
    ```
    """

    model: Type[Base] | str
    relationships: SymList = {}
    include: SymList = {}
    exclude: SymList = {}
    extras: Dict[str, type | dict] = {}
    all_optional: bool = True
    include_virtuals: bool = True
    use_dynamic_relationships: bool = True
    lazy: bool | None = None
    exclude_pk: bool = False
    exclude_timestamps = False
    auto_include_relationships = False

    @classmethod
    def render_model(cls, result, lazy_first_level: bool | None = None): ...

    @classmethod
    def render_json(
        cls,
        result,
        exclude: Optional[SymList] = None,
        include: Optional[SymList] = None,
        lazy_first_level: bool | None = None,
    ): ...


class RequestSchema(metaclass=_MetaSchema):
    """Base class for requests

    **Example:**
    ```
    class PostUpdate(RequestSchema):
        model = "Post"
        all_optional = True
        extras = {"messages": List[int]}
    ```
    """

    model: Type[Base] | str
    include: SymList = {}
    exclude: SymList = {}
    extras: Dict[str, type | dict] = {}
    all_optional: bool = False
    exclude_pk: bool = True
    exclude_timestamps = True

    # private, use ResponseSchema instead if you need to customize this
    relationships: SymList = {}
    include_virtuals: bool = False
    use_dynamic_relationships: bool = False
    lazy: bool = False
