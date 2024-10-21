from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa


@queryable
class Poly(Base):
    __tablename__ = "poly"
    id = sa.Column(sa.Integer, primary_key=True)
    type = sa.Column(sa.String)

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
    id = sa.Column(sa.Integer, sa.ForeignKey("poly.id"), primary_key=True)
    a = sa.Column(sa.String)

    __mapper_args__ = {"polymorphic_identity": "a"}

    @staticmethod
    def of_eqa(q: SelectModel, term: str):
        return q.filter(PolyA.a == term)


@queryable
class PolyB(Poly):
    __tablename__ = "poly_b"
    id = sa.Column(sa.Integer, sa.ForeignKey("poly.id"), primary_key=True)
    b = sa.Column(sa.String)

    __mapper_args__ = {"polymorphic_identity": "b"}

    @staticmethod
    def of_eqb(q: SelectModel, term):
        return q.filter(PolyB.b == term)
