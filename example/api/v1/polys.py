from typing import Annotated
from fastapi_solo import (
    Router,
    PaginatedResponse,
    select,
    IndexDep,
    CreateDep,
    RootTransactionDep,
    Transaction,
)
from example.models.poly import Poly, PolyA, PolyB
from example.schemas.poly import (
    PolyA2Response,
    PolyB2Response,
    PolyAResponse,
    PolyBResponse,
    AnyPoly,
)


router = Router()


@router.get("")
def get_all_polys(index: IndexDep[Poly]) -> PaginatedResponse[AnyPoly]:
    return index.execute()  # type: ignore


@router.post("/a", status_code=201, response_model=PolyAResponse)
def create_poly_a(
    post: PolyA2Response,
    create: CreateDep[PolyA],
):
    return create.execute(post)


@router.post("/b", status_code=201)
def create_poly_b(
    post: PolyB2Response,
    create: CreateDep[PolyB],
) -> PolyBResponse:
    return create.execute(post)


def scoped_query():
    return select(Poly).filter(Poly.type == "a")


@router.get("/complex", response_model=PaginatedResponse[AnyPoly])
def complex_get_all_a(index: IndexDep[Annotated[Poly, scoped_query]]):
    q = index.query.filter(PolyA.a.contains("a"))
    return index.paginate_query(
        q,
        before_render=lambda r: AnyPoly.render_json(r, exclude=["type"]),
    )


@router.post("/weird")
def weird_post(
    create: CreateDep[PolyA],
    tx: RootTransactionDep,
) -> AnyPoly:
    p = create.execute({"a": "asd"})  # only this will be saved
    tx.force_commit()
    PolyA(a="dsa").asave(create.db)

    with Transaction(create.db, nested=True) as nested:
        PolyA(a="zzz").asave(create.db)
        nested.force_rollback()
        PolyA(a="xxx").asave(create.db)
    tx.force_rollback()
    create.db.refresh(p)

    return p
