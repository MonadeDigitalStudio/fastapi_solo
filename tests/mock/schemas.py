from typing import List, Optional

from fastapi_solo.serialization.schemas import all_optional
from fastapi_solo.serialization.schema_models import (
    ResponseSchema,
    RequestSchema,
    response_schema,
    request_schema,
)
from tests.mock import models as m


class MessageUpdate(RequestSchema):
    __model__ = m.Message
    __all_optional__ = True
    tags: List[int]


class PostResponse(ResponseSchema):
    __model__ = "Post"
    __relationships__ = {
        "messages": {"tags"},
    }


class PostCreate(RequestSchema):
    __model__ = m.Post
    messages: Optional[List[int]]


@all_optional()
class PostUpdate(request_schema(m.Post, True)):
    messages: List[int]


MessageResponse = response_schema(
    m.Message,
    relationships=(
        "tags",
        {"post": {"messages": {"tags"}}},
    ),
)
