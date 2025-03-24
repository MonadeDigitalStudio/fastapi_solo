from fastapi_solo import ResponseSchema


class PolyAResponse(ResponseSchema):
    model = "PolyA"


class PolyBResponse(ResponseSchema):
    model = "PolyB"


class PolyA2Response(ResponseSchema):
    model = "PolyA"
    exclude = ["type"]


class PolyB2Response(ResponseSchema):
    model = "PolyB"
    exclude = ["type"]


class AnyPoly(PolyAResponse, PolyBResponse):
    pass
