from typing import TYPE_CHECKING
from fastapi_solo import Base, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.util import hybridproperty
from example.models.message import message_tag

if TYPE_CHECKING:
    from example.models.message import Message


@queryable
class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    @property
    def asd(self) -> int:
        return 555

    @hybridproperty
    def asd2(self):
        return "asd2" + self.name

    asd3: AssociationProxy[list[str]] = association_proxy("messages", "text")

    messages: Mapped[list["Message"]] = relationship(
        secondary=message_tag, back_populates="tags"
    )
