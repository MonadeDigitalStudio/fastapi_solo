from fastapi_solo import Base, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.util import hybridproperty
from example.models.message import message_tag


@queryable
class Tag(Base):
    __tablename__ = "tag"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)

    @property
    def asd(self) -> int:
        return 555

    @hybridproperty
    def asd2(self):
        return "asd2" + self.name

    asd3 = association_proxy("messages", "text")

    messages = relationship("Message", secondary=message_tag, back_populates="tags")
