from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship


@queryable
class Post(Base):
    __tablename__ = "post"
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String, nullable=False)

    messages = relationship("Message", back_populates="post")

    @staticmethod
    def of_ids(q: SelectModel, term: str):
        ids = [int(i) for i in term.split(",")]
        return q.filter(Post.id.in_(ids))

    @staticmethod
    def of_title_like(q: SelectModel, term: str):
        return q.filter(Post.title.contains(term))


@queryable("name")
class Tag(Base):
    __tablename__ = "tag"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, nullable=False)


message_tag = sa.Table(
    "message_tag",
    Base.metadata,
    sa.Column("message_id", sa.Integer, sa.ForeignKey("message.id"), primary_key=True),
    sa.Column("tag_id", sa.Integer, sa.ForeignKey("tag.id"), primary_key=True),
)


@queryable
class Message(Base):
    __tablename__ = "message"
    id = sa.Column(sa.Integer, primary_key=True)
    text = sa.Column(sa.String)
    post_id = sa.Column(sa.Integer, sa.ForeignKey("post.id"))
    post = relationship("Post", back_populates="messages")

    tags = relationship("Tag", secondary=message_tag)
