from logging import getLogger
from typing import Any
from inspect import iscoroutinefunction

log = getLogger("fastapi_solo")


class InjectedBackgroundTasks:
    def add_task(self, fn: Any, *args: Any, **kwargs: Any):
        if iscoroutinefunction(fn):
            log.error(
                f"Cannot run async functions from BackgroundTasks in this injection context, task {fn.__name__} will be ignored"
            )
            return
        log.info(f"Running BackgroundTask syncronously - {fn.__name__}")
        fn(*args, **kwargs)


def RuntimeType(fn) -> Any:
    class Special:
        def __class_getitem__(cls, item):
            return fn(item)

    return Special


def parse_bool(string: str):
    if isinstance(string, bool):
        return string
    string = (string or "").strip()
    if string == "true":
        return True
    elif string == "false":
        return False
    return None


def _void_callback() -> Any:
    # This is a void callback, it does nothing
    pass


VOID_CALLBACK = _void_callback
