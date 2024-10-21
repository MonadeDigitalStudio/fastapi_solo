from typing import List, Callable, Optional, Sequence, TypeVar, TYPE_CHECKING
from .config import FastapiSoloConfig
from sqlalchemy.orm import Query

if TYPE_CHECKING:
    from ..db import Session, SelectModel, Base

    T = TypeVar("T", bound=Base)


def paginate_query(
    db: "Session",
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
        data = db.exec(query).all()
        if before_render:
            data = before_render(data)
        return {"data": data}
    if isinstance(query, Query):
        count = query.count()  # type: ignore
    else:
        count: int = db.execute(query.count()).unique().scalar()  # type: ignore
    data = db.exec(query.paginate(page=page, size=size)).all()  # type: ignore
    if before_render:
        data = before_render(data)
    return paginate_result(data, count, page, size)


def paginate_result(
    result: Sequence, count: int, page: int, size: int | str | None = None
):
    """Generate a dict for render a PaginatedResponse from an already limited and offseted result list

    params:
    - result: the result list (already limited and offseted)
    - count: the total count of the result list
    - page: the current page rendered
    - size: the page size
    """
    if size is None:
        size = FastapiSoloConfig.pagination_size
    if size == "all":
        return {"data": result}

    assert isinstance(size, int)

    total_pages = (count // size) + 1
    if count % size == 0:
        total_pages -= 1
    return {
        "data": result,
        "meta": {
            "total": count,
            "pageSize": size,
            "totalPages": total_pages,
            "currentPage": page,
            "nextPage": page + 1 if page < total_pages else None,
            "previousPage": page - 1 if page > 1 else None,
        },
    }


def paginate_list(
    data: List,
    page: int,
    size: int | str | None = None,
):
    """Generate a dict for render a PaginatedResponse from a not paginated list

    params:
    - data: the data list
    - page: the page to render
    - size: the page size
    """
    if size is None:
        size = FastapiSoloConfig.pagination_size

    if size == "all":
        return {"data": data}

    index_from = (page - 1) * size
    index_to = (page) * size
    data_page = data[index_from:index_to]

    return paginate_result(data_page, len(data), page, size)
