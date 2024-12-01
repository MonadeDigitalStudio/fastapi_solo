from typing import Annotated, TypeVar, get_origin, get_args, TYPE_CHECKING
from fastapi import Depends

from .database import (
    AsyncSession,
    AsyncTransaction,
    get_async_root_transaction,
    get_async_db,
    Base,
)
from .solipsist import (
    AsyncIndex,
    AsyncShow,
    AsyncCreate,
    AsyncUpdate,
    AsyncDelete,
    get_async_index,
    get_async_show,
    get_async_create,
    get_async_update,
    get_async_delete,
)

from fastapi_solo.utils.misc import RuntimeType


AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_db)]  # type: ignore
AsyncRootTransactionDep = Annotated[
    AsyncTransaction, Depends(get_async_root_transaction)
]  # type: ignore


@RuntimeType
def AsyncIndexDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[AsyncIndex, Depends(get_async_index(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[AsyncIndex, Depends(get_async_index(model, get_query))]
    return Annotated[AsyncIndex, Depends(get_async_index(params))]


@RuntimeType
def AsyncShowDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[AsyncShow, Depends(get_async_show(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[AsyncShow, Depends(get_async_show(model, get_query))]
    return Annotated[AsyncShow, Depends(get_async_show(params))]


@RuntimeType
def AsyncCreateDep(params):  # type: ignore
    return Annotated[AsyncCreate, Depends(get_async_create(params))]


@RuntimeType
def AsyncUpdateDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[AsyncUpdate, Depends(get_async_update(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[AsyncUpdate, Depends(get_async_update(model, get_query))]
    return Annotated[AsyncUpdate, Depends(get_async_update(params))]


@RuntimeType
def AsyncDeleteDep(params):  # type: ignore
    if isinstance(params, tuple):
        model, get_query = params
        return Annotated[AsyncDelete, Depends(get_async_delete(model, get_query))]
    if get_origin(params) is Annotated:
        model, get_query = get_args(params)
        return Annotated[AsyncDelete, Depends(get_async_delete(model, get_query))]
    return Annotated[AsyncDelete, Depends(get_async_delete(params))]


if TYPE_CHECKING:  # pragma: no cover
    T = TypeVar("T", bound=Base)

    class AsyncSessionDep(AsyncSession): ...

    class AsyncRootTransactionDep(AsyncTransaction): ...

    class AsyncIndexDep(AsyncIndex[T]): ...

    class AsyncShowDep(AsyncShow[T]): ...

    class AsyncCreateDep(AsyncCreate[T]): ...

    class AsyncUpdateDep(AsyncUpdate[T]): ...

    class AsyncDeleteDep(AsyncDelete[T]): ...
