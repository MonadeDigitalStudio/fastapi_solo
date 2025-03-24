from typing import Any, Optional, Dict, List, Callable, Type
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.ext.asyncio import (
    AsyncSession as SqlAlchemyAsyncSession,
    async_object_session,
)
from fastapi import Depends, HTTPException
from pydantic import BaseModel


from ..utils.db import get_single_pk
from ..utils.config import FastapiSoloConfig
from ..db.database import Base, select
from ..router.router import Router, RespModel, VOID_CALLBACK, SelectModel
from ..serialization.schemas import PaginatedResponse
from .dependencies import (
    AsyncIndexDep,
    AsyncShowDep,
    AsyncCreateDep,
    AsyncUpdateDep,
    AsyncDeleteDep,
)


def _is_relationship_argument(cls, key, value):
    if (
        isinstance(value, list)
        and len(value) > 0
        and (isinstance(value[0], int) or isinstance(value[0], str))
    ):
        attr = getattr(cls, key)
        attr_type = getattr(attr, "property", None)
        if attr_type and isinstance(attr_type, RelationshipProperty):
            return True
    return False


async def _adecode_field(cls, db, key, value):
    if _is_relationship_argument(cls, key, value):
        # many to many relationship
        attr = getattr(cls, key)
        attr_type = getattr(attr, "property")
        rel_model = attr_type.mapper.class_
        if len(value) > 0:
            pk = get_single_pk(rel_model)
            rel_list = (await db.exec(select(rel_model).filter(pk.in_(value)))).all()
            if len(rel_list) != len(value):
                raise HTTPException(
                    400,
                    detail=f"Invalid {key} value. Invalid relationships",
                )
            value = rel_list
    return value


async def asave(
    self,
    db: Optional[SqlAlchemyAsyncSession] = None,
    update: BaseModel | Dict | Any = None,  # type: ignore
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

        db = async_object_session(self)
        assert db
    if update:
        if not isinstance(update, dict):
            update: dict = update.model_dump(exclude_unset=True, exclude_defaults=True)
        for key, value in update.items():

            value = await _adecode_field(self.__class__, db, key, value)
            setattr(self, key, value)
    db.add(self)
    if flush:
        await db.flush()
    return self


async def adelete(self, flush=True):
    """Delete the model from the database"""

    db = async_object_session(self)
    assert db
    await db.delete(self)
    if flush:
        await db.flush()


@classmethod
async def acreate(
    cls,
    db: SqlAlchemyAsyncSession,
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
        k: await _adecode_field(cls, db, k, v)
        for k, v in obj.items()
        if hasattr(cls, k)
    }
    model = cls(**obj)
    await model.asave(db, flush=flush)
    return model


Base.asave = asave
Base.adelete = adelete
Base.acreate = acreate


def agenerate_crud(
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
    """Generate all the CRUD routes for a model (async version)

    params:
    - model: the sqlalchemy model to use
    - response_schema: the pydantic response model to use, inferred from model if not provided
    - create_schema: the pydantic create model to use, inferred from model if not provided
    - update_schema: the pydantic update model to use, inferred from model if not provided
    - generate_[*]: boolean to generate or not the [*] route
    - [*]_dependencies: dependencies to add to the [*] route
    - dependencies: dependencies to add to all routes
    - get_query: an injectable query object to use as base for queries
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

        async def get_all_paginated(
            index: AsyncIndexDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                index.set_base_query(base_query)
            return await index.execute()

        self.add_api_route(
            "",
            get_all_paginated,
            methods=["GET"],
            response_model=PaginatedResponse[self.response_schema],  # type: ignore
            dependencies=[*dependencies, *get_all_dependencies],
        )
    # get one
    if generate_get:

        async def get_one(
            id,
            show: AsyncShowDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                show.set_base_query(base_query)
            return await show.execute(id)

        self.add_api_route(
            "/{id}",
            get_one,
            methods=["GET"],
            response_model=self.response_schema,  # type: ignore
            dependencies=[*dependencies, *get_dependencies],
        )
    # post
    if generate_post:
        request_model = self.create_schema

        async def create(
            obj: request_model,  # type: ignore
            create: AsyncCreateDep[self.model],  # type: ignore
        ):
            return await create.execute(obj)

        self.add_api_route(
            "",
            create,
            methods=["POST"],
            response_model=self.response_schema,  # type: ignore
            dependencies=[*dependencies, *post_dependencies],
        )
    # put
    if generate_put:
        request_model = self.update_schema

        async def update(
            id,
            obj: request_model,  # type: ignore
            update: AsyncUpdateDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                update.set_base_query(base_query)
            return await update.execute(id, obj)

        self.add_api_route(
            "/{id}",
            update,
            methods=["PUT"],
            response_model=self.response_schema,  # type: ignore
            dependencies=[*dependencies, *put_dependencies],
        )
    # delete
    if generate_delete:

        async def delete(
            id,
            delete: AsyncDeleteDep[self.model],  # type: ignore
            base_query: SelectModel = Depends(get_query),
        ):
            if base_query is not None:
                delete.set_base_query(base_query)
            return await delete.execute(id)

        self.add_api_route(
            "/{id}",
            delete,
            methods=["DELETE"],
            status_code=FastapiSoloConfig.delete_status_code,
            dependencies=[*dependencies, *delete_dependencies],
        )


Router.agenerate_crud = agenerate_crud  # type: ignore
