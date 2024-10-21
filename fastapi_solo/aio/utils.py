from typing import Callable, Optional, TypeVar, TYPE_CHECKING
from fastapi_solo.utils.pagination import paginate_result
from fastapi_solo.utils.config import FastapiSoloConfig


if TYPE_CHECKING:
    from .database import SelectModel, Base, AsyncSession

    T = TypeVar("T", bound=Base)


async def apaginate_query(
    db: "AsyncSession",
    query: "SelectModel[T]",
    page: int,
    size: int | str | None = None,
    before_render: Optional[Callable] = None,
):
    """Generate a dict for render a PaginatedResponse from a query object

    params:
    - db: the db session
    - query: the query object
    - page: the page to render
    - size: the page size
    - before_render: a function to call on the result before rendering
    """
    if size is None:
        size = FastapiSoloConfig.pagination_size
    if size == "all":
        data = (await db.exec(query)).all()
        if before_render:
            data = before_render(data)
        return {"data": data}

    count: int = (await db.execute(query.count())).unique().scalar()  # type: ignore
    data = (await db.exec(query.paginate(page=page, size=size))).all()
    if before_render:
        data = before_render(data)
    return paginate_result(data, count, page, size)
