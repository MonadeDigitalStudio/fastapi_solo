from typing import Annotated
from fastapi import Depends
from fastapi_solo import (
    Router,
    IndexDep,
    ShowDep,
    CreateDep,
    UpdateDep,
    DeleteDep,
    PaginatedResponse,
    select,
)
from tests.mock.models import Post, Tag, Message
from tests.mock.schemas import (
    PostResponse,
    PostCreate,
    PostUpdate,
    MessageUpdate,
    MessageResponse,
)

api_router = Router()

tag_router = Router(prefix="/tags")
message_router = Router(prefix="/messages")
post_router = Router(prefix="/posts")

tag_router.generate_crud(Tag)

message_router.generate_crud(
    Message, response_schema=MessageResponse, update_schema=MessageUpdate
)


@post_router.get("", response_model=PaginatedResponse[PostResponse])
def get_all_posts(index: IndexDep[Post]):
    return index.execute()


def scope():
    return select(Post).filter(Post.title.contains("test"))


@post_router.get("/scoped", response_model=PaginatedResponse[PostResponse])
def get_all_posts_scoped(index: IndexDep[Annotated[Post, scope]]):
    return index.execute()


@post_router.get("/scoped2", response_model=PaginatedResponse[PostResponse])
def get_all_posts_scoped2(index: IndexDep[Post, scope]):  # type: ignore
    return index.execute()


@post_router.get("/{id}/scoped", response_model=PostResponse)
def get_post_scoped(id: int, show: ShowDep[Annotated[Post, scope]]):
    return show.execute(id)


@post_router.get("/{id}/scoped2", response_model=PostResponse)
def get_post_scoped2(id: int, show: ShowDep[Post, scope]):  # type: ignore
    return show.execute(id)


@post_router.get("/{id}", response_model=PostResponse)
def get_post(id: int, show: ShowDep[Post]):
    return show.execute(id)


@post_router.post("", response_model=PostResponse, status_code=201)
def create_post(post: PostCreate, create: CreateDep[Post]):
    return create.execute(post)


@post_router.put("/{id}/scopedput", response_model=PostResponse)
def update_post_scoped(
    id: int, post: PostUpdate, update: UpdateDep[Annotated[Post, scope]]
):
    return update.execute(id, post)


@post_router.put("/{id}/scopedput", response_model=PostResponse)
def update_post_scoped2(id: int, post: PostUpdate, update: UpdateDep[Post, scope]):  # type: ignore
    return update.execute(id, post)


@post_router.put("/{id}", response_model=PostResponse)
def update_post(id: int, post: PostUpdate, update: UpdateDep[Post]):
    return update.execute(id, post)


@post_router.delete("/{id}/scopeddelete")
def delete_post_scoped(id: int, delete: DeleteDep[Annotated[Post, scope]]):
    return delete.execute(id)


@post_router.delete("/{id}/scopeddelete")
def delete_post_scoped2(id: int, delete: DeleteDep[Post, scope]):  # type: ignore
    return delete.execute(id)


@post_router.delete("/{id}")
def delete_post(id: int, delete: DeleteDep[Post]):
    return delete.execute(id)


api_router.include_router(post_router)
api_router.include_router(message_router)
api_router.include_router(tag_router)
