from typing import TYPE_CHECKING
from fastapi_solo import BaseWithTS, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship, mapped_column, Mapped

if TYPE_CHECKING:
    from example.models.message import Message


@queryable
class Post(BaseWithTS):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]

    messages: Mapped[list["Message"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

    @staticmethod
    def of_msg_txt(q: SelectModel, txt: str):
        from example.models.message import Message

        return q.join(Post.messages).filter(Message.text.contains(txt))

    @staticmethod
    def by_reverse_title(q: SelectModel, is_desc: bool):
        return q.order_by(Post.title if is_desc else sa.desc(Post.title))
