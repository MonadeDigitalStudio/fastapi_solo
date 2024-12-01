from typing import TYPE_CHECKING
from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship, mapped_column, Mapped

if TYPE_CHECKING:
    from example.models.tag import Tag
    from example.models.post import Post

message_tag = sa.Table(
    "message_tag",
    Base.metadata,
    sa.Column("message_id", sa.Integer, sa.ForeignKey("message.id")),
    sa.Column("tag_id", sa.Integer, sa.ForeignKey("tag.id")),
)


@queryable
class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str | None]
    post_id: Mapped[int] = mapped_column(sa.ForeignKey("post.id"))
    post: Mapped["Post"] = relationship(back_populates="messages")

    tags: Mapped[list["Tag"]] = relationship(
        secondary=message_tag, back_populates="messages"
    )

    @staticmethod
    def of_post_title(q: SelectModel, title: str):
        from example.models.post import Post

        return q.join(Message.post).filter(Post.title.contains(title))
