from fastapi_solo import ResponseSchema, RequestSchema
from example.models import tag as m


class Tag(ResponseSchema):
    model = m.Tag
    include = {
        "name": True,
        "asd": True,
        "asd2": True,
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
    model = m.Tag


class TagUpdate(RequestSchema):
    model = m.Tag
    all_optional = True
