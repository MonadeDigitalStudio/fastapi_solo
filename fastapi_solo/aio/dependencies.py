from typing import Annotated, TypeVar, TYPE_CHECKING
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


if TYPE_CHECKING:  # fixme: find a better way to type these
    T = TypeVar("T", bound=Base)

    class _FakeTypable:
        def __class_getitem__(cls, _): ...

    class AsyncSessionDep(AsyncSession): ...

    class AsyncRootTransactionDep(AsyncTransaction): ...

    class AsyncIndexDep(AsyncIndex, _FakeTypable): ...

    class AsyncShowDep(AsyncShow, _FakeTypable): ...

    class AsyncCreateDep(AsyncCreate, _FakeTypable): ...

    class AsyncUpdateDep(AsyncUpdate, _FakeTypable): ...

    class AsyncDeleteDep(AsyncDelete, _FakeTypable): ...

else:
    AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_db)]
    AsyncRootTransactionDep = Annotated[
        AsyncTransaction, Depends(get_async_root_transaction)
    ]

    @RuntimeType
    def AsyncIndexDep(params):
        if isinstance(params, tuple):
            model, get_query = params
            return Annotated[AsyncIndex, Depends(get_async_index(model, get_query))]
        return Annotated[AsyncIndex, Depends(get_async_index(params))]

    @RuntimeType
    def AsyncShowDep(params):
        if isinstance(params, tuple):
            model, get_query = params
            return Annotated[AsyncShow, Depends(get_async_show(model, get_query))]
        return Annotated[AsyncShow, Depends(get_async_show(params))]

    @RuntimeType
    def AsyncCreateDep(params):
        return Annotated[AsyncCreate, Depends(get_async_create(params))]

    @RuntimeType
    def AsyncUpdateDep(params):
        if isinstance(params, tuple):
            model, get_query = params
            return Annotated[AsyncUpdate, Depends(get_async_update(model, get_query))]
        return Annotated[AsyncUpdate, Depends(get_async_update(params))]

    @RuntimeType
    def AsyncDeleteDep(params):
        if isinstance(params, tuple):
            model, get_query = params
            return Annotated[AsyncDelete, Depends(get_async_delete(model, get_query))]
        return Annotated[AsyncDelete, Depends(get_async_delete(params))]


__all__ = [
    "AsyncSessionDep",
    "AsyncRootTransactionDep",
    "AsyncIndexDep",
    "AsyncShowDep",
    "AsyncCreateDep",
    "AsyncUpdateDep",
    "AsyncDeleteDep",
]
