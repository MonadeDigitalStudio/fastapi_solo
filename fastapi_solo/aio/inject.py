from typing import Any, Optional
from types import AsyncGeneratorType, GeneratorType
from inspect import signature, iscoroutinefunction, isasyncgenfunction
from fastapi import BackgroundTasks, Request
from fastapi.params import Depends
from pydantic.fields import FieldInfo
from fastapi_solo.utils.misc import InjectedBackgroundTasks


async def _aclose_yields(yields):
    for y in reversed(yields):
        try:
            if isinstance(y, AsyncGeneratorType):
                await anext(y)
            else:
                next(y)
        except StopAsyncIteration:
            pass
        except StopIteration:
            pass


async def _ainit_dep(dep, cache, yields):
    depfn: Any = _injector(dep, _cache=cache, _yields=yields)
    if isasyncgenfunction(depfn):
        val = depfn()
        yields.append(val)
        val = await anext(val)
    elif iscoroutinefunction(depfn):
        val = await depfn()
    else:
        val = depfn()

        if isinstance(val, GeneratorType):
            yields.append(val)
            val = next(val)
    return val


async def _aresolve_dep(dep, use_cache, cache, yields):
    if use_cache:
        if dep not in cache:
            cache[dep] = await _ainit_dep(dep, cache, yields)
        return cache[dep]
    else:
        return await _ainit_dep(dep, cache, yields)


async def _aresolve_dependencies(sign, kwargs, cache, yields):
    for key, p in sign.parameters.items():
        if key in kwargs:
            continue
        if isinstance(p.default, Depends):
            kwargs[key] = await _aresolve_dep(
                p.default.dependency or p.annotation,
                p.default.use_cache,
                cache,
                yields,
            )
        elif isinstance(p.default, FieldInfo):
            kwargs[key] = p.default.default
        elif p.annotation == Request:
            kwargs[key] = cache.get(Request)
        elif p.annotation == BackgroundTasks:
            kwargs[key] = cache.get(BackgroundTasks) or InjectedBackgroundTasks()
        elif hasattr(p.annotation, "__metadata__"):
            meta_deps = next(
                (m for m in p.annotation.__metadata__ if isinstance(m, Depends)), None
            )
            if meta_deps:
                kwargs[key] = await _aresolve_dep(
                    meta_deps.dependency or p.annotation.__origin__,
                    meta_deps.use_cache,
                    cache,
                    yields,
                )


def _injector_fn(fn, _cache, _yields):
    sign = signature(fn)

    async def wrapper(*args, **kwargs):
        cache = _cache if _cache is not None else {}
        yields = _yields if _yields is not None else []
        await _aresolve_dependencies(sign, kwargs, cache, yields)
        if isasyncgenfunction(fn):
            gen = fn(*args, **kwargs)
            res = await anext(gen)
            yields.append(gen)
        elif iscoroutinefunction(fn):
            res = await fn(*args, **kwargs)
        else:
            res = fn(*args, **kwargs)
            if isinstance(res, GeneratorType):
                yields.append(res)
                res = next(res)
        if _yields is None:
            await _aclose_yields(yields)
        return res

    return wrapper


def _injector(obj=None, *, overrides: Optional[dict] = None, _cache=None, _yields=None):
    if overrides is not None:
        if obj is None:
            return lambda obj: _injector(obj, _cache=overrides, _yields=_yields)
        else:
            return _injector(obj, _cache=overrides, _yields=_yields)
    return _injector_fn(obj, _cache, _yields)


def async_injector(obj=None, *, overrides: Optional[dict] = None) -> Any:
    """Decorator to allow FastAPI dependency injection in functions or classes outside of FastAPI routers

    **Example:**
    ```
    def get_db() -> Session:
        return Session()


    @injector
    def job(db: Session = Depends(get_db)):
        return db.exec(...).all()

    job()

    @injector(overrides={get_db: MockedSession()})
    def job2(db: Session = Depends(get_db)):
        return db.exec(...).all()

    job2()
    ```
    """
    return _injector(obj, overrides=overrides)
