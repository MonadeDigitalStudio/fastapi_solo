from fastapi_solo import ResponseSchema, RequestSchema
from example.models import tag as m


class Tag(ResponseSchema):
    __model__ = m.Tag
    __include__ = {
        "name": True,
        "messages": {
            "post_id": True,
            "text": True,
            "post": {
                "messages": {
                    "tags": {"asd2"},
                }
            },
        },
    }


class TagCreate(RequestSchema):
    __model__ = m.Tag


class TagUpdate(RequestSchema):
    __model__ = m.Tag
    __all_optional__ = True
