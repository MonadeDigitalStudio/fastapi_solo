from fastapi_solo import QueryModel, Session, select
from tests.mock.models import Post, Tag, Message
from sqlalchemy import desc
from sqlalchemy.orm.attributes import instance_state


def mock_data(db):
    p1 = Post(title="post").save(db)
    t1 = Tag(name="tag").save(db)
    t2 = Tag(name="tag2").save(db)
    m1 = Message(text="msg1", post_id=p1.id, tags=[t1, t2]).save(db)

    p2 = Post(title="post2").save(db)
    m2 = Message(text="msg2", post_id=p2.id, tags=[t1]).save(db)
    m3 = Message(text="msg3", post_id=p2.id, tags=[t2]).save(db)

    return (p1, p2, t1, t2, m1, m2, m3)


def test_query_class(db):
    assert isinstance(db, Session)
    q = db.query(Post)
    assert isinstance(q, QueryModel)
    assert isinstance(q.where(Post.id == 1), QueryModel)


def test_query_by(db):
    p1, p2, *_ = mock_data(db)

    pt = db.query(Post).query_by(title_like="2").all()
    assert len(pt) == 1
    pt = db.query(Post).query_by(title="post2").all()
    assert pt[0].id == p2.id

    Post.of_msg_txt = lambda q, txt: q.join(Post.messages).filter(Message.text == txt)

    pt = db.query(Post).query_by(msg_txt="msg1").all()
    assert len(pt) == 1
    assert pt[0].id == p1.id

    Post.of_tag_name = (
        lambda q, name: q.join(Post.messages)
        .join(Message.tags)
        .filter(Tag.name == name)
    )
    pt = db.query(Post).query_by(tag_name="tag").all()
    assert len(pt) == 2


def test_select_query_by(db):
    p1, p2, *_ = mock_data(db)

    q = select(Post).query_by(title_like="2")
    pt = db.exec(q).all()
    assert len(pt) == 1
    q = select(Post).query_by(id=p2.id)
    pt = db.exec(q).all()
    assert len(pt) == 1
    q = select(Post).query_by(title="post2")
    pt = db.exec(q).all()
    assert pt[0].id == p2.id

    Post.of_msg_txt = lambda q, txt: q.join(Post.messages).filter(Message.text == txt)

    q = select(Post).query_by(msg_txt="msg1")
    pt = db.exec(q).all()
    assert len(pt) == 1
    assert pt[0].id == p1.id

    Post.of_tag_name = (
        lambda q, name: q.join(Post.messages)
        .join(Message.tags)
        .filter(Tag.name == name)
    )
    q = select(Post).query_by(tag_name="tag")
    pt = db.exec(q).all()
    assert len(pt) == 2


def test_only_decorated_query_by(db):
    p1, p2, t1, t2, m1, m2, m3 = mock_data(db)

    q = select(Message).query_by(text="msg1")
    m = db.exec(q).all()
    count = db.exec(select(Message).count()).one()
    # Message has no queryable decorator, no filter should be applied
    assert len(m) == count


def test_sort_by(db):
    p1, p2, *_ = mock_data(db)
    pt = db.query(Post).sort("title").all()
    assert pt[0].id == p1.id
    assert pt[1].id == p2.id

    pt = db.query(Post).sort("-title").all()
    assert pt[0].id == p2.id
    assert pt[1].id == p1.id

    Post.by_msg_txt = lambda q, is_desc: q.join(Post.messages).order_by(
        desc(Message.text) if is_desc else Message.text
    )
    pt = db.query(Post).sort("msg_txt").all()
    assert pt[0].id == p1.id
    assert pt[1].id == p2.id
    pt = db.query(Post).sort("-msg_txt").all()
    assert pt[0].id == p2.id
    assert pt[1].id == p1.id


def test_select_sort_by(db):
    p1, p2, *_ = mock_data(db)
    q = select(Post).sort("title")
    pt = db.exec(q).all()
    assert pt[0].id == p1.id
    assert pt[1].id == p2.id

    q = select(Post).sort("-title")
    pt = db.exec(q).all()
    assert pt[0].id == p2.id
    assert pt[1].id == p1.id

    Post.by_msg_txt = (
        lambda q, is_desc: q.join(Post.messages)
        .order_by(desc(Message.text) if is_desc else Message.text)
        .distinct()
    )
    q = select(Post).sort("msg_txt")
    pt = db.exec(q).all()
    assert pt[0].id == p1.id
    assert pt[1].id == p2.id
    q = select(Post).sort("-msg_txt")
    pt = db.exec(q).all()
    assert pt[0].id == p2.id
    assert pt[1].id == p1.id


def test_includes(db):
    mock_data(db)
    pt = db.query(Post).includes("messages.tags").first()
    assert "messages" not in instance_state(pt).unloaded
    assert "tags" not in instance_state(pt.messages[0]).unloaded


def test_select_includes(db):
    mock_data(db)
    q = select(Post).includes("messages.tags")
    pt = db.exec(q).first()
    assert "messages" not in instance_state(pt).unloaded
    assert "tags" not in instance_state(pt.messages[0]).unloaded


def test_select_includes_all(db):
    mock_data(db)
    q = select(Post).includes("*")
    pt = db.exec(q).first()
    assert "messages" not in instance_state(pt).unloaded
    assert "tags" not in instance_state(pt.messages[0]).unloaded
    assert "messages" in instance_state(pt.messages[0].tags[0]).unloaded
