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
    model = m.Message
    all_optional = True
    tags: List[int]


class PostResponse(ResponseSchema):
    model = "Post"
    relationships = {
        "messages": {"tags"},
    }


class PostCreate(RequestSchema):
    model = m.Post
    messages: Optional[List[int]]


@all_optional()
class PostUpdate(request_schema(m.Post, True)):
    messages: List[int]


MessageResponse = response_schema(
    m.Message,
    relationships=(
        "tags",
        {"post": {"messages": ["tags"]}},
    ),
)
