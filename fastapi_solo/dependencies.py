from typing import Annotated, TypeVar, TYPE_CHECKING, get_origin, get_args
from fastapi import Depends

from .db import (
    Session,
    Transaction,
    get_db,
    get_root_transaction,
    Base,
)
from .router.solipsist import (
    Index,
    Show,
    Create,
    Update,
    Delete,
    get_index,
    get_show,
    get_create,
    get_update,
    get_delete,
    get_swagger_filters,
)

from .utils.misc import RuntimeType


SessionDep = Annotated[Session, Depends(get_db)]  # type: ignore
RootTransactionDep = Annotated[Transaction, Depends(get_root_transaction)]  # type: ignore


@RuntimeType
def IndexDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[Index, Depends(get_index(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[Index, Depends(get_index(model, get_query))]
    return Annotated[Index, Depends(get_index(params))]


@RuntimeType
def ShowDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[Show, Depends(get_show(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[Show, Depends(get_show(model, get_query))]
    return Annotated[Show, Depends(get_show(params))]


@RuntimeType
def CreateDep(params):  # type: ignore
    return Annotated[Create, Depends(get_create(params))]


@RuntimeType
def UpdateDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[Update, Depends(get_update(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[Update, Depends(get_update(model, get_query))]
    return Annotated[Update, Depends(get_update(params))]


@RuntimeType
def DeleteDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[Delete, Depends(get_delete(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[Delete, Depends(get_delete(model, get_query))]
    return Annotated[Delete, Depends(get_delete(params))]


@RuntimeType
def SwaggerFiltersDep(params):
    if not isinstance(params, tuple):
        params = [params]
    return Annotated[None, Depends(get_swagger_filters(*params))]


if TYPE_CHECKING:  # pragma: no cover
    T = TypeVar("T", bound=Base)

    class SessionDep(Session):
        """Dependency to get the current database session in a FastAPI route"""

        ...

    class RootTransactionDep(Transaction):
        """Dependency to get the current database transaction in a FastAPI route"""

        ...

    class IndexDep(Index[T]):
        """Dependency to get a solipsistic index handler

        properties:
        - db: the db session
        - includes: the includes from query params
        - filters: the filters from query params
        - sort: the sort from query params
        - page: the page from query params
        - size: the size from query params

        - query: the select query object filtered, sorted and with includes, all from query params
        - base_query: the select query object without filters, sort and includes

        ```
        @router.get("")
        def get_all_posts(
            index: IndexDep[Post],
        ) -> PaginatedResponse[PostResponse]:
            return index.execute()
        ```
        """

        ...

    class ShowDep(Show[T]):
        """Dependency to get a solipsistic show handler

        properties:
        - db: the db session
        - includes: the includes from query params
        - query: the select query object for the model

        ```
        @router.get("/{id}")
        def get_post(id: int, show: ShowDep[Post]) -> PostResponse:
            return show.execute(id)
        ```
        """

        ...

    class CreateDep(Create[T]):
        """Dependency to get a solipsistic create handler

        properties:
        - db: the db session
        - includes: the includes from query params
        - query: the select query object for the model

        ```
        @router.post("", status_code=201)
        def create_post(post: PostCreate, create: CreateDep[Post]) -> PostResponse:
            return create.execute(post)
        ```
        """

        ...

    class UpdateDep(Update[T]):
        """Dependency to get a solipsistic update handler

        properties:
        - db: the db session
        - includes: the includes from query params
        - query: the select query object for the model

        ```
        @router.put("/{id}")
        def update_post(id: int, post: PostUpdate, update: UpdateDep[Post]) -> PostResponse:
            return update.execute(id, post)
        ```
        """

        ...

    class DeleteDep(Delete[T]):
        """Dependency to get a solipsistic delete handler

        properties:
        - db: the db session
        - query: the select query object for the model

        ```
        @router.delete("/{id}", status_code=204)
        def delete_post(id, delete: DeleteDep[Post]):
            return delete.execute(id)
        ```
        """

        ...
