from typing import Any


class OpenStruct:
    def __init__(self, obj: dict | None = None):
        self.__dict = {} if obj is None else obj

    @staticmethod
    def __from_obj(obj):
        if isinstance(obj, OpenStruct):
            return obj
        elif isinstance(obj, dict):
            return OpenStruct(obj)
        elif isinstance(obj, list):
            return [OpenStruct.__from_obj(i) for i in obj]
        return obj

    def __repr__(self):
        return f"{self.__dict}"

    def __getattr__(self, key) -> Any:
        if key in self.__dict:
            return OpenStruct.__from_obj(self.__dict[key])
        raise AttributeError(f"No such attribute: {key}")

    def __setattr__(self, key, value):
        if key == "_OpenStruct__dict":
            return super().__setattr__(key, value)
        self.__dict[key] = value

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)
