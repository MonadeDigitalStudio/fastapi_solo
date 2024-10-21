from fastapi_solo import response_schema, request_schema, select
from tests.mock.models import Post, Tag, Message
from typing import Optional


def mock_data(db):
    p1 = Post(title="post").save(db)
    t1 = Tag(name="tag").save(db)
    t2 = Tag(name="tag2").save(db)
    m1 = Message(text="msg1", post_id=p1.id, tags=[t1, t2]).save(db)

    p2 = Post(title="post2").save(db)
    m2 = Message(text="msg2", post_id=p2.id, tags=[t1]).save(db)
    m3 = Message(text="msg3", post_id=p2.id, tags=[t2]).save(db)
    return (p1, p2, t1, t2, m1, m2, m3)


def test_render_schema_base(db):
    p1, *_ = mock_data(db)
    schema = response_schema(Post)
    json = schema.render_json(p1)
    assert json["id"] == p1.id
    assert json["title"] == p1.title
    assert json.get("messages") == None


def test_render_schema_with_relationships(db):
    p1, *_ = mock_data(db)
    schema = response_schema(Post, relationships={"messages": {"tags"}})
    json = schema.render_json(p1)
    assert json["id"] == p1.id
    assert json["title"] == p1.title
    assert len(json["messages"]) == len(p1.messages)
    assert len(json["messages"][0]["tags"]) == len(p1.messages[0].tags)


def test_render_schema_with_relationships_dynamic_includes(db):
    p1, *_ = mock_data(db)
    schema = response_schema(Post, relationships={"messages": {"tags"}})
    msg_len = len(p1.messages)
    tags_len = len(p1.messages[0].tags)
    db.expire_all()

    p = db.exec(select(Post).find_id(p1.id)).one()
    json = schema.render_json(p)
    assert json["id"] == p.id
    assert json["title"] == p.title
    assert len(json["messages"]) == msg_len
    assert json["messages"][0].get("tags") == None

    p = db.exec(select(Post).includes("messages.tags").find_id(p1.id)).one()
    json = schema.render_json(p)
    assert json["id"] == p.id
    assert json["title"] == p.title
    assert len(json["messages"]) == msg_len
    assert len(json["messages"][0]["tags"]) == tags_len


def test_render_schema_with_extra_fields(db):
    p1, *_ = mock_data(db)
    schema = response_schema(
        Post, relationships={"messages"}, extras={"messages": {"extra_field": str}}
    )
    p1.messages[0].extra_field = "extra"

    json = schema.render_json(p1)
    assert json["messages"][0]["extraField"] == "extra"


def test_render_schema_with_all_lazy(db):
    p1, *_ = mock_data(db)
    schema = response_schema(Post, relationships={"messages"})
    db.expire_all()

    p = db.exec(select(Post).find_id(p1.id)).one()
    json = schema.render_json(p, lazy_first_level=True)
    assert json.get("messages") == None

    p = db.exec(select(Post).includes("messages").find_id(p1.id)).one()
    json = schema.render_json(p, lazy_first_level=True)
    assert len(json["messages"]) == len(p.messages)


def test_post_schema():
    schema = request_schema(Post)
    assert schema.__annotations__.get("id") == None
    assert schema.__annotations__["title"] == str
    assert schema.model_fields["title"].default != None


def test_put_schema():
    schema = request_schema(Post, True)
    assert schema.__annotations__.get("id") == None
    assert schema.__annotations__["title"] == Optional[str]
    assert schema.model_fields["title"].default == None
