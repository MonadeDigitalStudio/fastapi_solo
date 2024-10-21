from fastapi_solo import ResponseSchema


class PolyAResponse(ResponseSchema):
    __model__ = "PolyA"


class PolyBResponse(ResponseSchema):
    __model__ = "PolyB"


class PolyA2Response(ResponseSchema):
    __model__ = "PolyA"
    __exclude__ = ["type"]


class PolyB2Response(ResponseSchema):
    __model__ = "PolyB"
    __exclude__ = ["type"]


class AnyPoly(PolyAResponse, PolyBResponse):
    pass
