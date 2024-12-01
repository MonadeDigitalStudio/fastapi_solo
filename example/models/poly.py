from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column


@queryable
class Poly(Base):
    __tablename__ = "poly"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str | None]

    __mapper_args__ = {
        "polymorphic_on": "type",
        "with_polymorphic": "*",
    }

    @staticmethod
    def of_eqtype(q: SelectModel, term: str):
        return q.filter(Poly.type == term)


@queryable
class PolyA(Poly):
    __tablename__ = "poly_a"
    id: Mapped[int] = mapped_column(sa.ForeignKey("poly.id"), primary_key=True)
    a: Mapped[str | None]

    __mapper_args__ = {"polymorphic_identity": "a"}

    @staticmethod
    def of_eqa(q: SelectModel, term: str):
        return q.filter(PolyA.a == term)


@queryable
class PolyB(Poly):
    __tablename__ = "poly_b"
    id: Mapped[int] = mapped_column(sa.ForeignKey("poly.id"), primary_key=True)
    b: Mapped[str | None]

    __mapper_args__ = {"polymorphic_identity": "b"}

    @staticmethod
    def of_eqb(q: SelectModel, term):
        return q.filter(PolyB.b == term)
