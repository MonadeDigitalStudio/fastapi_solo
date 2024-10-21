from fastapi_solo import ResponseSchema
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
