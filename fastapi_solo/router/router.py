from typing import (
    Callable,
    Optional,
    List,
    Type,
    Union,
    TYPE_CHECKING,
)
from fastapi import APIRouter, Depends, params
from enum import Enum
from pydantic import BaseModel
from ..serialization.schemas import (
    PaginatedResponse,
)
from ..serialization.schema_models import (
    response_schema as gen_response_schema,
    request_schema as gen_request_schema,
)
from ..db.database import Base, SelectModel
from ..utils.misc import VOID_CALLBACK
from ..utils.config import FastapiSoloConfig
from ..dependencies import (
    IndexDep,
    ShowDep,
    CreateDep,
    UpdateDep,
    DeleteDep,
)

if TYPE_CHECKING:
    from ..serialization.schema_models import ResponseSchema, RequestSchema

RespModel = Type[Union[BaseModel, "ResponseSchema", "RequestSchema"]]

ID_PATH = "/{id}"


class Router(APIRouter):
    def __init__(
        self,
        prefix: str = "",
        tags: Optional[List[str | Enum]] = None,
        dependencies: Optional[List[params.Depends]] = [],
        response_model_exclude_unset=True,
        response_model_exclude_defaults=False,
        **kwargs,
    ):
        self.response_model_exclude_unset = response_model_exclude_unset
        self.response_model_exclude_defaults = response_model_exclude_defaults
        super().__init__(
            prefix=prefix,
            tags=tags,
            dependencies=dependencies,
            **kwargs,
        )

    def generate_crud(
        self,
        model: Type[Base],
        *,
        response_schema: Optional[RespModel] = None,
        create_schema: Optional[RespModel] = None,
        update_schema: Optional[RespModel] = None,
        generate_get: bool = True,
        generate_get_all: bool = True,
        generate_post: bool = True,
        generate_put: bool = True,
        generate_delete: bool = True,
        get_dependencies: List = [],
        get_all_dependencies: List = [],
        post_dependencies: List = [],
        put_dependencies: List = [],
        delete_dependencies: List = [],
        dependencies: List = [],
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
        auto_include_relationships: bool = False,
    ):
        """Generate all the CRUD routes for a model

        params:
        - model: the sqlalchemy model to use
        - response_schema: the pydantic response model to use, inferred from model if not provided
        - create_schema: the pydantic create model to use, inferred from model if not provided
        - update_schema: the pydantic update model to use, inferred from model if not provided
        - generate_[*]: boolean to generate or not the [*] route
        - [*]_dependencies: dependencies to add to the [*] route
        - dependencies: dependencies to add to all routes
        - get_query: an injectable query object to use as base for queries
        - auto_include_relationships: include first level relationships in response schema (works only if response_schema is not provided)
        """
        self._init_generator(
            model,
            response_schema=response_schema,
            create_schema=create_schema,
            update_schema=update_schema,
            auto_include_relationships=auto_include_relationships,
        )
        # get all
        if generate_get_all:
            self._default_get_all(
                dependencies=[
                    *dependencies,
                    *get_all_dependencies,
                ],
                get_query=get_query,
            )
        # get one
        if generate_get:
            self._default_get(
                dependencies=[*dependencies, *get_dependencies], get_query=get_query
            )
        # post
        if generate_post:
            self._default_post(dependencies=[*dependencies, *post_dependencies])
        # put
        if generate_put:
            self._default_put(
                dependencies=[*dependencies, *put_dependencies], get_query=get_query
            )
        # delete
        if generate_delete:
            self._default_delete(
                dependencies=[*dependencies, *delete_dependencies], get_query=get_query
            )

    def _init_generator(
        self,
        model: Type[Base],
        response_schema: Optional[RespModel] = None,
        create_schema: Optional[RespModel] = None,
        update_schema: Optional[RespModel] = None,
        auto_include_relationships: bool = False,
    ):
        self.model = model
        self.response_schema = response_schema
        self.create_schema = create_schema
        self.update_schema = update_schema
        if not response_schema:
            self.response_schema = gen_response_schema(
                model, auto_include_relationships=auto_include_relationships
            )
        if not create_schema:
            self.create_schema = gen_request_schema(model)
        if not update_schema:
            self.update_schema = gen_request_schema(model, all_optional=True)

    def add_api_route(
        self,
        *args,
        **kwargs,
    ):
        kwargs["response_model_exclude_unset"] = self.response_model_exclude_unset
        kwargs["response_model_exclude_defaults"] = self.response_model_exclude_defaults
        return super().add_api_route(
            *args,
            **kwargs,
        )

    def _default_get_all(
        self,
        response_model: Optional[RespModel] = None,
        dependencies: Optional[List] = None,
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
    ):
        self.add_api_route(
            "",
            self._get_all_paginated(get_query),
            methods=["GET"],
            response_model=PaginatedResponse[response_model or self.response_schema],  # type: ignore
            dependencies=dependencies,
        )

    def _default_get(
        self,
        response_model: Optional[RespModel] = None,
        dependencies: Optional[List] = None,
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
    ):
        self.add_api_route(
            ID_PATH,
            self._get_one(get_query),
            methods=["GET"],
            response_model=response_model or self.response_schema,
            dependencies=dependencies,
        )

    def _default_post(
        self,
        request_model: Optional[RespModel] = None,
        response_model: Optional[RespModel] = None,
        dependencies: Optional[List] = None,
    ):
        self.add_api_route(
            "",
            self._create(request_model),
            methods=["POST"],
            status_code=201,
            response_model=response_model or self.response_schema,
            dependencies=dependencies,
        )

    def _default_put(
        self,
        request_model: Optional[RespModel] = None,
        response_model: Optional[RespModel] = None,
        dependencies: Optional[List] = None,
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
    ):
        self.add_api_route(
            ID_PATH,
            self._update(request_model, get_query),
            methods=["PUT"],
            response_model=response_model or self.response_schema,
            dependencies=dependencies,
        )

    def _default_delete(
        self,
        dependencies: Optional[List] = None,
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
    ):
        self.add_api_route(
            ID_PATH,
            self._delete(get_query),
            methods=["DELETE"],
            status_code=FastapiSoloConfig.delete_status_code,
            dependencies=dependencies,
        )

    def _get_all_paginated(self, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
        def get_all_paginated(
            index: IndexDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                index.set_base_query(base_query)
            return index.execute()

        return get_all_paginated

    def _get_one(self, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
        def get_one(
            id,
            show: ShowDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                show.set_base_query(base_query)
            return show.execute(id)

        return get_one

    def _create(self, request_model: Optional[RespModel] = None):
        request_model = request_model or self.create_schema

        def create(
            obj: request_model,  # type: ignore
            create: CreateDep[self.model],  # type: ignore
        ):
            return create.execute(obj)

        return create

    def _update(
        self,
        request_model: Optional[RespModel] = None,
        get_query: Callable[..., SelectModel] = VOID_CALLBACK,
    ):
        request_model = request_model or self.update_schema

        def update(
            id,
            obj: request_model,  # type: ignore
            update: UpdateDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                update.set_base_query(base_query)
            return update.execute(id, obj)

        return update

    def _delete(self, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
        def delete(
            id,
            delete: DeleteDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                delete.set_base_query(base_query)
            return delete.execute(id)

        return delete
