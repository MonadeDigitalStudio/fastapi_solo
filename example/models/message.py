from fastapi_solo import Base, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship


message_tag = sa.Table(
    "message_tag",
    Base.metadata,
    sa.Column("message_id", sa.Integer, sa.ForeignKey("message.id")),
    sa.Column("tag_id", sa.Integer, sa.ForeignKey("tag.id")),
)


@queryable
class Message(Base):
    __tablename__ = "message"
    id = sa.Column(sa.Integer, primary_key=True)
    text = sa.Column(sa.String)
    post_id = sa.Column(sa.Integer, sa.ForeignKey("post.id"), nullable=False)
    post = relationship("Post", back_populates="messages")

    tags = relationship("Tag", secondary=message_tag, back_populates="messages")

    @staticmethod
    def of_post_title(q: SelectModel, title: str):
        return q.join(Message.post).filter(Post.title.contains(title))


from example.models.post import Post
