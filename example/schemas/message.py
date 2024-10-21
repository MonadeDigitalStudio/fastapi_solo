from typing import List, Optional
from fastapi_solo import (
    ResponseSchema,
    RequestSchema,
)


class MessageCreate(RequestSchema):
    __model__ = "Message"

    tags: Optional[List[int]]


class MessageUpdate(RequestSchema):
    __model__ = "Message"
    __all_optional__ = True

    tags: List[int]


class Message(ResponseSchema):
    __model__ = "Message"
    __relationships__ = {
        "tags": {"messages"},
        "post": {"messages"},
    }
