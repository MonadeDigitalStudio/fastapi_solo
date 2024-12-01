from fastapi_solo import Router, PaginatedResponse
from fastapi_solo.aio import (
    AsyncIndexDep,
    AsyncShowDep,
    AsyncCreateDep,
    AsyncUpdateDep,
    AsyncDeleteDep,
)
from example.models.message import Message
from example.schemas import message as schema

router = Router()


@router.get("", response_model=PaginatedResponse[schema.Message])
async def get_all_messages(index: AsyncIndexDep[Message]):
    return await index.execute()


@router.get("/{id}", response_model=schema.Message)
async def get_message(id: int, show: AsyncShowDep[Message]):
    return await show.execute(id)


@router.post("", response_model=schema.Message, status_code=201)
async def create_message(post: schema.MessageCreate, create: AsyncCreateDep[Message]):
    return await create.execute(post)


@router.put("/{id}", response_model=schema.Message)
async def update_message(
    id: int, post: schema.MessageUpdate, update: AsyncUpdateDep[Message]
):
    return await update.execute(id, post)


@router.delete("/{id}")
async def delete_message(id: int, delete: AsyncDeleteDep[Message]):
    return await delete.execute(id)
