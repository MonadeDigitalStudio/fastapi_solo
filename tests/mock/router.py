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


@post_router.get("/", response_model=PaginatedResponse[PostResponse])
def get_all_posts(solo: IndexDep[Post]):
    return solo.execute()


def scope():
    return select(Post).filter(Post.title.contains("test"))


@post_router.get("/scoped", response_model=PaginatedResponse[PostResponse])
def get_all_posts_scoped(solo: IndexDep[Post, scope]):
    return solo.execute()


@post_router.get("/{id}", response_model=PostResponse)
def get_post(id: int, solo: ShowDep[Post]):
    return solo.execute(id)


@post_router.post("/", response_model=PostResponse, status_code=201)
def create_post(post: PostCreate, solo: CreateDep[Post]):
    return solo.execute(post)


@post_router.put("/{id}", response_model=PostResponse)
def update_post(id: int, post: PostUpdate, solo: UpdateDep[Post]):
    return solo.execute(id, post)


@post_router.delete("/{id}", status_code=204)
def delete_post(id: int, solo: DeleteDep[Post]):
    return solo.execute(id)


api_router.include_router(post_router)
api_router.include_router(message_router)
api_router.include_router(tag_router)
