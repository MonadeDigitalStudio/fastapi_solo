from fastapi_solo import (
    Router,
    PaginatedResponse,
    IndexDep,
    ShowDep,
    CreateDep,
    UpdateDep,
    DeleteDep,
    paginate_result,
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
def get_all_posts(
    index: IndexDep[Post],
) -> PaginatedResponse[PostResponse]:
    return index.execute()  # type: ignore


@router.get("/enriched", response_model=PaginatedResponse[PostEnriched])
def get_enriched_posts(
    index: IndexDep[Post],
):
    result = index.db.exec(index.query.paginate(index.page, index.size)).all()
    count = index.db.scalar(index.query.count()) or 0

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
def get_post(id: int, show: ShowDep[Post]) -> PostResponse:
    return show.execute(id)


@router.post("", status_code=201)
def create_post(post: PostCreate, create: CreateDep[Post]) -> PostResponse:
    return create.execute(post)


@router.put("/{id}")
def update_post(id: int, post: PostUpdate, update: UpdateDep[Post]) -> PostResponse:
    return update.execute(id, post)


@router.delete("/{id}", status_code=204)
def delete_post(id: int, delete: DeleteDep[Post]):
    delete.execute(id)
