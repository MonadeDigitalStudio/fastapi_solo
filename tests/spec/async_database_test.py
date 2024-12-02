import pytest
from fastapi import HTTPException
from fastapi_solo import BaseSchema, select
from fastapi_solo.aio import AsyncTransaction
from fastapi_solo.exc import DbException
from tests.mock.models import Post, Tag, Message
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSessionTransaction
from sqlalchemy import insert


class RollbackException(Exception):
    pass


@pytest.mark.asyncio
async def test_create_with_relationship(async_db):
    p1 = await Post.acreate(async_db, title="post")
    t = await Tag.acreate(async_db, name="tag")
    m1 = await Message.acreate(async_db, text="msg", post_id=p1.id, tags=[t.id])
    assert isinstance(m1.tags[0], Tag)
    assert m1.tags[0].id == t.id


@pytest.mark.asyncio
async def test_create_with_not_existing_relationship(async_db):
    p1 = await Post.acreate(async_db, title="post")
    t = await Tag.acreate(async_db, name="tag")
    with pytest.raises(HTTPException):
        await Message.acreate(async_db, text="msg", post_id=p1.id, tags=[t.id, 99])


@pytest.mark.asyncio
async def test_delete(async_db):
    p1 = await Post.acreate(async_db, title="post")
    await p1.adelete()
    assert await async_db.get(Post, p1.id) is None


@pytest.mark.asyncio
async def test_update(async_db):
    p1 = await Post.acreate(async_db, title="post")
    await p1.asave(update={"title": "new title"})
    await async_db.refresh(p1)
    assert p1.title == "new title"


@pytest.mark.asyncio
async def test_update_with_pydantic(async_db):
    class PostUpdate(BaseSchema):
        title: str

    p1 = await Post.acreate(async_db, title="post")
    await p1.asave(update=PostUpdate(title="new title"))
    await async_db.refresh(p1)
    assert p1.title == "new title"


@pytest.mark.asyncio
async def test_find_or_create_by_full_match(async_db):
    p1 = await Post.acreate(async_db, title="post")
    p2 = await async_db.find_or_create(Post, title="post")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_find_or_create_by_pl(async_db):
    p1 = await Post.acreate(async_db, title="post")
    p2 = await async_db.find_or_create(Post, id=p1.id, title="post2")
    assert p1.id == p2.id
    assert p2.title == "post"


@pytest.mark.asyncio
async def test_find_or_create_by_not_full_match(async_db):
    p1 = await Post.acreate(async_db, title="post", rating=5)
    p2 = await async_db.find_or_create(Post, title="post", rating=4)
    assert p1.id != p2.id


@pytest.mark.asyncio
async def test_find_or_create_by_not_unique(async_db):
    await Post.acreate(async_db, title="post")
    await Post.acreate(async_db, title="post")
    with pytest.raises(MultipleResultsFound):
        await async_db.find_or_create(Post, title="post")


@pytest.mark.asyncio
async def test_find_or_create_by_find_by(async_db):
    p1 = await Post.acreate(async_db, title="post", rating=5)
    p2 = await async_db.find_or_create(Post, find_by=["title"], title="post", rating=4)
    assert p1.id == p2.id
    assert p2.rating == 5
    p2 = await async_db.find_or_create(
        Post, find_by=["rating"], title="post2", rating=5
    )
    assert p1.id == p2.id
    assert p2.title == "post"


@pytest.mark.asyncio
async def test_find_or_create_by_find_by_not_match(async_db):
    p1 = await Post.acreate(async_db, title="post", rating=5)
    p2 = await async_db.find_or_create(Post, find_by=["title"], title="post2", rating=4)
    assert p1.id != p2.id
    assert p2.rating == 4


@pytest.mark.asyncio
async def test_upsert_find_match(async_db):
    p1 = await Post.acreate(async_db, title="post", rating=5)
    p2 = await async_db.upsert(Post, find_by=["title"], title="post")
    p3 = await async_db.upsert(Post, find_by=["rating"], rating=5)
    assert p1.id == p2.id and p2.id == p3.id


@pytest.mark.asyncio
async def test_upsert_with_update(async_db):
    p1 = await async_db.upsert(Post, find_by=["title"], title="post", rating=3)
    assert p1.rating == 3
    p2 = await async_db.upsert(Post, find_by=["title"], title="post", rating=5)
    assert p1.id == p2.id
    assert p1.rating == 5

    p3 = await async_db.upsert(Post, find_by=["title"], title="post", rating=4)
    assert p3.id == p3.id
    assert p3.rating == 4


@pytest.mark.asyncio
async def test_upsert_without_required_field(async_db):
    with pytest.raises(DbException):
        await async_db.upsert(Post, rating=4)


@pytest.mark.asyncio
async def test_upsert_not_unique(async_db):
    await Post.acreate(async_db, title="post")
    await Post.acreate(async_db, title="post")
    with pytest.raises(MultipleResultsFound):
        await async_db.upsert(Post, find_by=["title"], title="post", rating=4)


@pytest.mark.asyncio
async def test_exec(async_db):
    r1 = await async_db.exec(insert(Post).values(title="post"))
    r2 = await async_db.execute(insert(Post).values(title="post"))
    assert r1.__class__ == r2.__class__
    r1 = await async_db.exec(select(Post).where(Post.title == "post"))
    r2 = await async_db.execute(select(Post).where(Post.title == "post"))
    assert r1.__class__ != r2.__class__


@pytest.mark.asyncio
async def test_transaction_rollback(async_db):
    with pytest.raises(RollbackException):
        async with AsyncTransaction(async_db, nested=True):
            p1 = await Post.acreate(async_db, id=1, title="post")
            raise RollbackException()
    r = await async_db.exec(select(Post.id).where(Post.id == 1))
    assert r.first() is None


@pytest.mark.asyncio
async def test_nesting_transactions(async_db):
    async with AsyncTransaction(async_db, nested=True) as trs1:
        p1 = await Post.acreate(async_db, title="post")
        try:
            async with AsyncTransaction(async_db) as trs2:
                p2 = await Post.acreate(async_db, title="post2")
                assert trs1.tx == trs2.tx
                raise RollbackException()
        except RollbackException:
            pass
        # rollbacked main transaction too
        assert await async_db.get(Post, p1.id) is None
        assert await async_db.get(Post, p2.id) is None


@pytest.mark.asyncio
async def test_nesting_transactions2(async_db):
    with pytest.raises(RollbackException):
        async with AsyncTransaction(async_db, nested=True):
            p1 = await Post.acreate(async_db, id=1, title="post")
            try:
                async with AsyncTransaction(async_db, nested=True):
                    await Post.acreate(async_db, id=2, title="post2")
                    raise RollbackException()
            except RollbackException:
                pass
            assert await async_db.get(Post, 1) is not None
            assert await async_db.get(Post, 2) is None
            raise RollbackException()
        assert await async_db.get(Post, p1.id) is None


@pytest.mark.asyncio
async def test_force_rollback_using_root_transaction(async_db):
    async with AsyncTransaction(async_db) as trs:
        p1 = await Post.acreate(async_db, id=1, title="post")
        await trs.force_rollback()
        assert await async_db.get(Post, 1) is None


@pytest.mark.asyncio
async def test_force_commit(async_db, mocker):
    mock = mocker.patch.object(AsyncSessionTransaction, "commit")
    async with AsyncTransaction(async_db) as trs:
        await Post.acreate(async_db, title="post")
        await trs.force_commit()
        assert mock.call_count == 1
