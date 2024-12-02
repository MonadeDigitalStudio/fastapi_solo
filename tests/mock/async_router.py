from typing import Annotated
from fastapi_solo import (
    Router,
    PaginatedResponse,
    select,
)
from fastapi_solo.aio import (
    AsyncIndexDep,
    AsyncShowDep,
    AsyncCreateDep,
    AsyncUpdateDep,
    AsyncDeleteDep,
)
from tests.mock.models import Post, Tag, Message
from tests.mock.schemas import (
    PostResponse,
    PostCreate,
    PostUpdate,
)

async_api_router = Router(prefix="/async")
post_router = Router(prefix="/posts")


@post_router.get("", response_model=PaginatedResponse[PostResponse])
async def async_get_all_posts(index: AsyncIndexDep[Post]):
    return await index.execute()


def scope():
    return select(Post).filter(Post.title.contains("test"))


@post_router.get("/scoped", response_model=PaginatedResponse[PostResponse])
async def get_all_posts_scoped(index: AsyncIndexDep[Annotated[Post, scope]]):
    return await index.execute()


@post_router.get("/scoped2", response_model=PaginatedResponse[PostResponse])
async def get_all_posts_scoped2(index: AsyncIndexDep[Post, scope]):  # type: ignore
    return await index.execute()


@post_router.get("/{id}/scoped", response_model=PostResponse)
async def get_post_scoped(id: int, show: AsyncShowDep[Annotated[Post, scope]]):
    return await show.execute(id)


@post_router.get("/{id}/scoped2", response_model=PostResponse)
async def get_post_scoped2(id: int, show: AsyncShowDep[Post, scope]):  # type: ignore
    return await show.execute(id)


@post_router.get("/{id}", response_model=PostResponse)
async def get_post(id: int, show: AsyncShowDep[Post]):
    return await show.execute(id)


@post_router.post("", response_model=PostResponse, status_code=201)
async def create_post(post: PostCreate, create: AsyncCreateDep[Post]):
    return await create.execute(post)


@post_router.put("/{id}/scopedput", response_model=PostResponse)
async def update_post_scoped(
    id: int, post: PostUpdate, update: AsyncUpdateDep[Annotated[Post, scope]]
):
    return await update.execute(id, post)


@post_router.put("/{id}/scopedput", response_model=PostResponse)
async def update_post_scoped2(id: int, post: PostUpdate, update: AsyncUpdateDep[Post, scope]):  # type: ignore
    return await update.execute(id, post)


@post_router.put("/{id}", response_model=PostResponse)
async def update_post(id: int, post: PostUpdate, update: AsyncUpdateDep[Post]):
    return await update.execute(id, post)


@post_router.delete("/{id}/scopeddelete")
async def delete_post_scoped(id: int, delete: AsyncDeleteDep[Annotated[Post, scope]]):
    return await delete.execute(id)


@post_router.delete("/{id}/scopeddelete")
async def delete_post_scoped2(id: int, delete: AsyncDeleteDep[Post, scope]):  # type: ignore
    return await delete.execute(id)


@post_router.delete("/{id}")
async def delete_post(id: int, delete: AsyncDeleteDep[Post]):
    return await delete.execute(id)


async_api_router.include_router(post_router)
