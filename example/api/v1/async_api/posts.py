from fastapi_solo import Router, PaginatedResponse, paginate_result
from fastapi_solo.aio import (
    AsyncIndexDep,
    AsyncShowDep,
    AsyncCreateDep,
    AsyncUpdateDep,
    AsyncDeleteDep,
)
from example.models.post import Post
from example.schemas.post import (
    Post as PostResponse,
    PostCreate,
    PostUpdate,
    PostEnriched,
)

router = Router()


@router.get("")
async def get_all_posts(
    index: AsyncIndexDep[Post],
) -> PaginatedResponse[PostResponse]:
    return await index.execute()  # type: ignore


@router.get("/enriched", response_model=PaginatedResponse[PostEnriched])
async def get_enriched_posts(
    index: AsyncIndexDep[Post],
):
    result = (await index.db.exec(index.query.paginate(index.page, index.size))).all()
    count = await index.db.scalar(index.query.count()) or 0

    for post in result:
        for message in post.messages:
            message.extra_field = f"extra-{message.id}"

    return paginate_result(
        result,
        count,
        index.page,
        index.size,
    )


@router.get("/{id}")
async def get_post(id: int, show: AsyncShowDep[Post]) -> PostResponse:
    return await show.execute(id)  # type: ignore


@router.post("", status_code=201)
async def create_post(post: PostCreate, create: AsyncCreateDep[Post]) -> PostResponse:
    return await create.execute(post)  # type: ignore


@router.put("/{id}")
async def update_post(
    id: int, post: PostUpdate, update: AsyncUpdateDep[Post]
) -> PostResponse:
    return await update.execute(id, post)  # type: ignore


@router.delete("/{id}", status_code=204)
async def delete_post(id: int, delete: AsyncDeleteDep[Post]):
    await delete.execute(id)
