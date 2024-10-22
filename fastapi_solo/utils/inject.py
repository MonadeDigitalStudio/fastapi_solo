from typing import Annotated, Any, Optional, get_args, get_origin
from types import GeneratorType
from inspect import signature
from fastapi import Request, BackgroundTasks
from fastapi.params import Depends
from pydantic.fields import FieldInfo
from .misc import InjectedBackgroundTasks


def _close_yields(yields):
    for y in reversed(yields):
        try:
            next(y)
        except StopIteration:
            pass


def _init_dep(dep, cache, yields):
    val = _injector(dep, _cache=cache, _yields=yields)()  # type: ignore
    if isinstance(val, GeneratorType):
        yields.append(val)
        val = next(val)
    return val


def _resolve_dep(dep, use_cache, cache, yields):
    if use_cache:
        if dep not in cache:
            cache[dep] = _init_dep(dep, cache, yields)
        return cache[dep]
    else:
        return _init_dep(dep, cache, yields)


def _resolve_dependencies(sign, kwargs, cache, yields):
    for key, p in sign.parameters.items():
        if key in kwargs:
            continue

        if isinstance(p.default, Depends):
            kwargs[key] = _resolve_dep(
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
        elif get_origin(p.annotation) is Annotated:
            d_type, meta_deps = get_args(p.annotation)
            if isinstance(meta_deps, Depends):
                kwargs[key] = _resolve_dep(
                    meta_deps.dependency or d_type,
                    meta_deps.use_cache,
                    cache,
                    yields,
                )


def _injector_fn(fn, _cache, _yields):
    sign = signature(fn)

    def wrapper(*args, **kwargs):
        cache = _cache if _cache is not None else {}
        yields = _yields if _yields is not None else []
        _resolve_dependencies(sign, kwargs, cache, yields)
        res = fn(*args, **kwargs)
        if _yields is None:
            _close_yields(yields)
        return res

    return wrapper


def _injector(obj=None, *, overrides: Optional[dict] = None, _cache=None, _yields=None):
    if overrides is not None:
        if obj is None:
            return lambda obj: _injector(obj, _cache=overrides, _yields=_yields)
        else:
            return _injector(obj, _cache=overrides, _yields=_yields)
    return _injector_fn(obj, _cache, _yields)


def injector(obj=None, *, overrides: Optional[dict] = None) -> Any:
    """Decorator to allow FastAPI dependency injection in functions or classes outside of FastAPI routers

    **Example:**
    ```
    def get_db() -> Session:
        return Session()


    @injector
    def job(db: Session = SessionDep):
        return db.exec(...).all()

    job()

    @injector(overrides={get_db: MockedSession()})
    def job2(db: Session = SessionDep):
        return db.exec(...).all()

    job2()
    ```
    """
    return _injector(obj, overrides=overrides)
