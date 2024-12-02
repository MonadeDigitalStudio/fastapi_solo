from fastapi import HTTPException
import pytest
from fastapi_solo import Base, BaseSchema, select, Transaction
from fastapi_solo.exc import DbException
from tests.mock.models import Post, Tag, Message
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy import insert
from sqlalchemy.orm.session import SessionTransaction


class RollbackException(Exception):
    pass


def test_get_model_by_reflect(db):
    assert Base.get_model("Tag") == Tag
    assert Base.get_model("Post") == Post
    assert Base.get_model("Message") == Message


def test_get_not_existing_model_by_reflect(db):
    with pytest.raises(DbException):
        Base.get_model("not_existing_model")


def test_create_with_relationship(db):
    p1 = Post.create(db, title="post")
    t = Tag.create(db, name="tag")
    m1 = Message.create(db, text="msg", post_id=p1.id, tags=[t.id])
    assert isinstance(m1.tags[0], Tag)
    assert m1.tags[0].id == t.id


def test_create_with_not_existing_relationship(db):
    p1 = Post.create(db, title="post")
    t = Tag.create(db, name="tag")
    with pytest.raises(HTTPException):
        m1 = Message.create(db, text="msg", post_id=p1.id, tags=[t.id, 99])


def test_delete(db):
    p1 = Post.create(db, title="post")
    p1.delete()
    assert db.get(Post, p1.id) is None


def test_update(db):
    p1 = Post.create(db, title="post")
    p1.save(update={"title": "new title"})
    db.refresh(p1)
    assert p1.title == "new title"


def test_update_with_pydantic(db):
    class PostUpdate(BaseSchema):
        title: str

    p1 = Post.create(db, title="post")
    p1.save(update=PostUpdate(title="new title"))
    db.refresh(p1)
    assert p1.title == "new title"


def test_find_or_create_by_full_match(db):
    p1 = Post.create(db, title="post")
    p2 = db.find_or_create(Post, title="post")
    assert p1.id == p2.id


def test_find_or_create_by_pl(db):
    p1 = Post.create(db, title="post")
    p2 = db.find_or_create(Post, id=p1.id, title="post2")
    assert p1.id == p2.id
    assert p2.title == "post"


def test_find_or_create_by_not_full_match(db):
    p1 = Post.create(db, title="post", rating=5)
    p2 = db.find_or_create(Post, title="post", rating=4)
    assert p1.id != p2.id


def test_find_or_create_by_not_unique(db):
    Post.create(db, title="post")
    Post.create(db, title="post")
    with pytest.raises(MultipleResultsFound):
        db.find_or_create(Post, title="post")


def test_find_or_create_by_find_by(db):
    p1 = Post.create(db, title="post", rating=5)
    p2 = db.find_or_create(Post, find_by=["title"], title="post", rating=4)
    assert p1.id == p2.id
    assert p2.rating == 5
    p2 = db.find_or_create(Post, find_by=["rating"], title="post2", rating=5)
    assert p1.id == p2.id
    assert p2.title == "post"


def test_find_or_create_by_find_by_not_match(db):
    p1 = Post.create(db, title="post", rating=5)
    p2 = db.find_or_create(Post, find_by=["title"], title="post2", rating=4)
    assert p1.id != p2.id
    assert p2.rating == 4


def test_upsert_find_match(db):
    p1 = Post.create(db, title="post", rating=5)
    p2 = db.upsert(Post, find_by=["title"], title="post")
    p3 = db.upsert(Post, find_by=["rating"], rating=5)
    assert p1.id == p2.id and p2.id == p3.id


def test_upsert_with_update(db):
    p1 = db.upsert(Post, find_by=["title"], title="post", rating=3)
    assert p1.rating == 3
    p2 = db.upsert(Post, find_by=["title"], title="post", rating=5)
    assert p1.id == p2.id
    assert p1.rating == 5

    p3 = db.upsert(Post, find_by=["title"], title="post", rating=4)
    assert p3.id == p3.id
    assert p3.rating == 4


def test_upsert_without_required_field(db):
    with pytest.raises(DbException):
        db.upsert(Post, rating=4)


def test_upsert_not_unique(db):
    Post.create(db, title="post")
    Post.create(db, title="post")
    with pytest.raises(MultipleResultsFound):
        db.upsert(Post, find_by=["title"], title="post", rating=4)


def test_exec(db):
    r1 = db.exec(insert(Post).values(title="post"))
    r2 = db.execute(insert(Post).values(title="post"))
    assert r1.__class__ == r2.__class__
    r1 = db.exec(select(Post).where(Post.title == "post"))
    r2 = db.execute(select(Post).where(Post.title == "post"))
    assert r1.__class__ != r2.__class__


def test_transaction_rollback(db):
    with pytest.raises(RollbackException):
        with Transaction(db, nested=True):
            p1 = Post.create(db, title="post")
            raise RollbackException()
    assert db.exec(select(Post.id).where(Post.id == p1.id)).first() is None


def test_nesting_transactions(db):
    with Transaction(db) as trs1:
        p1 = Post.create(db, title="post")
        try:
            with Transaction(db) as trs2:
                p2 = Post.create(db, title="post2")
                assert trs1.tx == trs2.tx
                raise RollbackException()
        except RollbackException:
            pass
        # rollbacked main transaction too
        assert db.get(Post, p1.id) is None
        assert db.get(Post, p2.id) is None


def test_nesting_transactions2(db):
    with pytest.raises(RollbackException):
        with Transaction(db, nested=True):
            p1 = Post.create(db, title="post")
            try:
                with Transaction(db, nested=True):
                    p2 = Post.create(db, title="post2")
                    raise RollbackException()
            except:
                pass
            assert db.get(Post, p1.id) is not None
            assert db.get(Post, p2.id) is None
            raise RollbackException()
        assert db.get(Post, p1.id) is None


def test_force_rollback_using_root_transaction(db):
    with Transaction(db) as trs:
        p1 = Post.create(db, title="post")
        trs.force_rollback()
        assert db.get(Post, p1.id) is None


def test_force_commit(db, mocker):
    mock = mocker.patch.object(SessionTransaction, "commit")
    with Transaction(db) as trs:
        Post.create(db, title="post")
        trs.force_commit()
        assert mock.call_count == 2
