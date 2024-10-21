from fastapi_solo import BaseWithTS, SelectModel, queryable
import sqlalchemy as sa
from sqlalchemy.orm import relationship


@queryable
class Post(BaseWithTS):
    __tablename__ = "post"
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String, nullable=False)

    messages = relationship(
        "Message", back_populates="post", cascade="all, delete-orphan"
    )

    @staticmethod
    def of_msg_txt(q: SelectModel, txt: str):
        return q.join(Post.messages).filter(Message.text.contains(txt))

    @staticmethod
    def by_reverse_title(q: SelectModel, is_desc: bool):
        return q.order_by(Post.title if is_desc else sa.desc(Post.title))


from example.models.message import Message
