from typing import Any, Optional, Dict
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.ext.asyncio import (
    AsyncSession as SqlAlchemyAsyncSession,
    async_object_session,
)
from fastapi import HTTPException
from pydantic import BaseModel


from ..utils.db import get_single_pk
from ..db.database import Base, select


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
