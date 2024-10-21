from typing import List, Optional
from fastapi_solo import RequestSchema, ResponseSchema, BaseSchema, all_optional


@all_optional
class PostUpdate(BaseSchema):
    title: str
    messages: List[int]


class Post(ResponseSchema):
    __model__ = "Post"
    __include__ = (
        "id",
        "title",
        {
            "messages": (
                "id",
                "text",
                {
                    "tags": {"id", "name"},
                    "post": {"id", "title"},
                },
            )
        },
    )
    __extras__ = {
        "messages": {"tags": {"asd3": List[str]}},
    }


class PostCreate(RequestSchema):
    __model__ = "Post"
    messages: Optional[List[int]]


class PostEnriched(ResponseSchema):
    __model__ = "Post"
    __relationships__ = {
        "messages": {"tags", "post"},
    }
    extras = {"messages": {"extra_field": str}}
