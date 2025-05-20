from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, relationship, mapped_column


@queryable
class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    rating: Mapped[int] = mapped_column(default=0)
    json_field: Mapped[dict] = mapped_column(sa.JSON, default={})

    messages: Mapped[list["Message"]] = relationship(back_populates="post")

    @staticmethod
    def of_ids(q: SelectModel, term: str):
        ids = [int(i) for i in term.split(",")]
        return q.filter(Post.id.in_(ids))

    @staticmethod
    def of_title_like(q: SelectModel, term: str):
        return q.filter(Post.title.contains(term))

    @staticmethod
    def of_json_filter(q: SelectModel, key: str, value: str):
        return q.filter(Post.json_field[key].icontains(value))

    @staticmethod
    def by_json_order(q: SelectModel, key: str, is_desc: bool):
        field = Post.json_field[key]
        if is_desc:
            field = field.desc()
        return q.order_by(field)


message_tag = sa.Table(
    "message_tag",
    Base.metadata,
    sa.Column("message_id", sa.Integer, sa.ForeignKey("message.id"), primary_key=True),
    sa.Column("tag_id", sa.Integer, sa.ForeignKey("tag.id"), primary_key=True),
)


@queryable("name")
class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    messages: Mapped[list["Message"]] = relationship(
        secondary=message_tag, back_populates="tags"
    )


class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    text: Mapped[str]
    post_id: Mapped[int] = mapped_column(sa.ForeignKey("post.id"))
    post: Mapped["Post"] = relationship(back_populates="messages")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=message_tag, back_populates="messages"
    )
