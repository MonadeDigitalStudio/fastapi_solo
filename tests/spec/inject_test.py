from typing import Annotated
from fastapi_solo import injector, PaginationParams
from fastapi_solo.utils.inject import InjectedBackgroundTasks
from fastapi import BackgroundTasks, Depends
from pydantic import Field
from tests.mock.router import get_all_posts


def test_injection():
    def dep1():
        return 1

    def dep2():
        yield 2

    @injector
    def fn(x, a: Annotated[int, Depends(dep1)], b=Depends(dep2)):
        return a + b + x

    assert fn(3) == 6


def test_nested_injection():
    def dep1():
        return 1

    def dep2(one=Depends(dep1)):
        yield 2 + one

    class Dep3:
        def __init__(self, two=Depends(dep2)):
            self.two = two

        def exec(self):
            return self.two + 3

    @injector
    def fn(x, a: Dep3 = Depends(), a2=Depends(Dep3)):
        return a.exec() + a2.exec() + x

    assert fn(4) == 16


def test_singleton_caching():
    a = 0

    def dep1():
        nonlocal a
        a += 1

    def dep2(x=Depends(dep1), y=Depends(dep1)):
        nonlocal a
        a += 1

    @injector
    def fn(val, x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == val

    fn(2)
    fn(4)


def test_no_cache():
    a = 0

    def dep1():
        nonlocal a
        a += 1

    def dep2(x=Depends(dep1), y=Depends(dep1, use_cache=False)):
        nonlocal a
        a += 1

    @injector
    def fn(val, x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == val

    fn(3)
    fn(6)


def test_generators_cleanup():
    a = 0

    def dep1():
        nonlocal a
        a += 1
        yield
        a -= 1

    def dep2(x=Depends(dep1)):
        nonlocal a
        a += 1
        yield
        a -= 1

    @injector
    def fn(x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == 2

    fn()
    assert a == 0


def test_generators_cleanup_with_exception():
    a = 0

    def dep1():
        nonlocal a
        a += 1
        return

    def dep2(x=Depends(dep1)):
        nonlocal a
        a += 1
        try:
            yield
        finally:
            a -= 1

    @injector
    def fn(x=Depends(dep2), y=Depends(dep1)):
        nonlocal a
        assert a == 2
        raise ValueError("test")

    try:
        fn()
    except ValueError as e:
        assert str(e) == "test"
    assert a == 1


def test_kwargs_overriding():
    def dep1():
        return 1

    def dep2():
        yield 2

    @injector
    def fn(x, a=Depends(dep1), b=Depends(dep2)):
        return a + b + x

    assert fn(3, a=3, b=3) == 9
    assert fn(3, a=3) == 8


def test_pydantic_field_defaults():
    def dep1():
        return 1

    @injector
    def fn(a: int = Field(3), b=Depends(dep1)):
        return a + b

    assert fn() == 4
    assert fn(a=2) == 3


def test_injection_overrides():
    def dep1():
        return 1

    def dep2():
        yield 2

    @injector(overrides={dep1: 3})
    def fn(x, a=Depends(dep1), b=Depends(dep2)):
        return a + b + x

    assert fn(3) == 8


def test_inject_router():
    @injector(
        overrides={
            PaginationParams: PaginationParams(page=1, size=10),
        }
    )
    def fn(a=Depends(get_all_posts)):
        return a

    res = fn()
    data = res["data"]
    meta = res["meta"]
    assert len(data) == 0
    assert meta["pageSize"] == 10
    assert meta["currentPage"] == 1


def test_inject_background_tasks():
    @injector
    def fn(t: BackgroundTasks):
        assert isinstance(t, InjectedBackgroundTasks)

        def task():
            raise ValueError("test")

        t.add_task(task)

    try:
        fn()
    except ValueError as e:
        assert str(e) == "test"
