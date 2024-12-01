from fastapi_solo import Router, PaginatedResponse
from fastapi_solo.aio import (
    AsyncIndexDep,
    AsyncShowDep,
    AsyncCreateDep,
    AsyncUpdateDep,
    AsyncDeleteDep,
)
from example.models.tag import Tag
from example.schemas import tag as s

router = Router()


@router.get("", response_model=PaginatedResponse[s.Tag])
async def get_all_tags(index: AsyncIndexDep[Tag]):
    return await index.execute()


@router.get("/{id}", response_model=s.Tag)
async def get_tag(id: int, show: AsyncShowDep[Tag]):
    return await show.execute(id)


@router.post("", response_model=s.Tag, status_code=201)
async def create_tag(post: s.TagCreate, create: AsyncCreateDep[Tag]):
    return await create.execute(post)


@router.put("/{id}", response_model=s.Tag)
async def update_tag(id: int, post: s.TagUpdate, update: AsyncUpdateDep[Tag]):
    return await update.execute(id, post)


@router.delete("/{id}")
async def delete_tag(id: int, delete: AsyncDeleteDep[Tag]):
    return await delete.execute(id)
