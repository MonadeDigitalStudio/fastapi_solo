from typing import List, Optional
from fastapi_solo import (
    ResponseSchema,
    RequestSchema,
)


class MessageCreate(RequestSchema):
    model = "Message"

    tags: Optional[List[int]]


class MessageUpdate(RequestSchema):
    model = "Message"
    all_optional = True

    tags: List[int]


class Message(ResponseSchema):
    model = "Message"
    relationships = {
        "tags": {"messages"},
        "post": {"messages"},
    }
