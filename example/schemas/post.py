from typing import List, Optional
from fastapi_solo import RequestSchema, ResponseSchema, BaseSchema, all_optional


@all_optional
class PostUpdate(BaseSchema):
    title: str
    messages: List[int]


class Post(ResponseSchema):
    model = "Post"
    include = (
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
    extras = {
        "messages": {"tags": {"asd3": List[str]}},
    }


class PostCreate(RequestSchema):
    model = "Post"
    messages: Optional[List[int]]


class PostEnriched(ResponseSchema):
    model = "Post"
    relationships = {
        "messages": {"tags", "post"},
    }
    extras = {"messages": {"extra_field": str}}
