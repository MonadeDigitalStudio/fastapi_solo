import pytest
from typing import Annotated
from fastapi_solo import PaginationParams
from fastapi_solo.aio import async_injector
from fastapi_solo.utils.inject import InjectedBackgroundTasks
from fastapi import BackgroundTasks, Depends
from pydantic import Field
from tests.mock.router import get_all_posts


@pytest.mark.asyncio
async def test_injection():
    def dep1():
        return 1

    async def dep2():
        yield 2

    @async_injector
    async def fn(x, a: Annotated[int, Depends(dep1)], b=Depends(dep2)):
        return a + b + x

    assert await fn(3) == 6


@pytest.mark.asyncio
async def test_nested_injection():
    def dep1():
        return 1

    async def dep2(one=Depends(dep1)):
        yield 2 + one

    class Dep3:
        def __init__(self, two=Depends(dep2)):
            self.two = two

        def exec(self):
            return self.two + 3

    @async_injector
    async def fn(x, a: Dep3 = Depends(), a2=Depends(Dep3)):
        return a.exec() + a2.exec() + x

    assert await fn(4) == 16


@pytest.mark.asyncio
async def test_singleton_caching():
    a = 0

    def dep1():
        nonlocal a
        a += 1

    async def dep2(x=Depends(dep1), y=Depends(dep1)):
        nonlocal a
        a += 1

    @async_injector
    async def fn(val, x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == val

    await fn(2)
    await fn(4)


@pytest.mark.asyncio
async def test_no_cache():
    a = 0

    def dep1():
        nonlocal a
        a += 1

    async def dep2(x=Depends(dep1), y=Depends(dep1, use_cache=False)):
        nonlocal a
        a += 1

    @async_injector
    async def fn(val, x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == val

    await fn(3)
    await fn(6)


@pytest.mark.asyncio
async def test_generators_cleanup():
    a = 0

    async def dep1():
        nonlocal a
        a += 1
        yield
        a -= 1

    async def dep2(x=Depends(dep1)):
        nonlocal a
        a += 1
        yield
        a -= 1

    @async_injector
    async def fn(x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == 2

    await fn()
    assert a == 0


@pytest.mark.asyncio
async def test_generators_cleanup_with_exception():
    a = 0

    async def dep1():
        nonlocal a
        a += 1
        return

    async def dep2(x=Depends(dep1)):
        nonlocal a
        a += 1
        try:
            yield
        finally:
            a -= 1

    @async_injector
    async def fn(x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == 2
        raise ValueError("test")

    try:
        await fn()
    except ValueError as e:
        assert str(e) == "test"

    assert a == 1


@pytest.mark.asyncio
async def test_kwargs_overriding():
    def dep1():
        return 1

    async def dep2():
        yield 2

    @async_injector
    async def fn(x, a=Depends(dep1), b=Depends(dep2)):
        return a + b + x

    assert await fn(3, a=3, b=3) == 9
    assert await fn(3, a=3) == 8


@pytest.mark.asyncio
async def test_pydantic_field_defaults():
    def dep1():
        return 1

    @async_injector
    async def fn(a: int = Field(3), b=Depends(dep1)):
        return a + b

    assert await fn() == 4
    assert await fn(a=2) == 3


@pytest.mark.asyncio
async def test_injection_overrides():
    def dep1():
        return 1

    async def dep2():
        yield 2

    @async_injector(overrides={dep1: 3})
    async def fn(x, a=Depends(dep1), b=Depends(dep2)):
        return a + b + x

    assert await fn(3) == 8


@pytest.mark.asyncio
async def test_inject_router():
    @async_injector(
        overrides={
            PaginationParams: PaginationParams(page=1, size=10),
        }
    )
    async def fn(a=Depends(get_all_posts)):
        return a

    res = await fn()
    data = res["data"]
    meta = res["meta"]
    assert len(data) == 0
    assert meta["pageSize"] == 10
    assert meta["currentPage"] == 1


@pytest.mark.asyncio
async def test_inject_background_tasks():
    @async_injector
    async def fn(t: BackgroundTasks):
        assert isinstance(t, InjectedBackgroundTasks)

        def task():
            raise ValueError("test")

        t.add_task(task)

    try:
        await fn()
    except ValueError as e:
        assert str(e) == "test"
