import pytest
from tests.mock.models import Post, Tag, Message
import fastapi_solo.aio.testing as r
from fastapi_solo.utils.testing import a_list_of


async def mock_data(db):
    p1 = await Post(title="post").asave(db)
    t1 = await Tag(name="tag").asave(db)
    t2 = await Tag(name="tag2").asave(db)
    m1 = await Message(text="msg1", post_id=p1.id, tags=[t1, t2]).asave(db)

    p2 = await Post(title="post2").asave(db)
    m2 = await Message(text="msg2", post_id=p2.id, tags=[t1]).asave(db)
    m3 = await Message(text="msg3", post_id=p2.id, tags=[t2]).asave(db)
    return (p1, p2, t1, t2, m1, m2, m3)


@pytest.mark.asyncio
async def test_get_all(async_db, async_client):
    await mock_data(async_db)
    response = await async_client.get("/async/posts?include=messages")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": a_list_of(
                {
                    "id": int,
                    "messages": a_list_of({"id": int}),
                }
            ),
            "meta": {
                "total": 2,
                "currentPage": 1,
                "totalPages": 1,
            },
        },
    )

    # test pagination
    response = await async_client.get("/async/posts?page[size]=1")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [{"id": 1}],
            "meta": {
                "total": 2,
                "currentPage": 1,
                "totalPages": 2,
                "nextPage": 2,
            },
        },
    )

    # test filters
    response = await async_client.get("/async/posts?filter[title]=post2")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"data": [{"id": 2}]},
    )

    # test sort
    response = await async_client.get("/async/posts?sort=-title")
    assert response.status_code == 200
    assert r.match(response.json(), {"data": [{"id": 2}, {"id": 1}]})

    # test includes
    response = await async_client.get("/async/posts?include=messages.tags")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": a_list_of(
                {
                    "id": int,
                    "messages": a_list_of(
                        {
                            "id": int,
                            "tags": a_list_of({"id": int}),
                        },
                    ),
                },
            )
        },
    )


@pytest.mark.asyncio
async def test_get_all_scoped(async_db, async_client):
    await mock_data(async_db)
    response = await async_client.get("/async/posts/scoped")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [],
        },
    )

    p = await Post.acreate(async_db, title="test1")
    response = await async_client.get("/async/posts/scoped")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [{"id": p.id}],
        },
    )


@pytest.mark.asyncio
async def test_get_one(async_db, async_client):
    await mock_data(async_db)
    response = await async_client.get("/async/posts/1")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"id": 1},
    )
    # test relationship after first level are not loaded
    assert response.json().get("messages") is None


@pytest.mark.asyncio
async def test_get_one_not_found(async_db, async_client):
    response = await async_client.get("/async/posts/1")
    assert response.status_code == 404
    assert r.match(response.json(), {"detail": "Post not found"})


@pytest.mark.asyncio
async def test_get_one_with_includes(async_db, async_client):
    await mock_data(async_db)
    response = await async_client.get("/async/posts/1?include=messages.tags")

    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "id": 1,
            "messages": [
                {
                    "id": 1,
                    "tags": [{"id": 1}, {"id": 2}],
                },
            ],
        },
    )


@pytest.mark.asyncio
async def test_get_one_without_includes(async_db, async_client):
    await mock_data(async_db)
    response = await async_client.get("/async/posts/1")

    assert response.status_code == 200

    json = response.json()
    assert r.match(
        json,
        {"id": 1},
    )
    assert not hasattr(json, "messages")


@pytest.mark.asyncio
async def test_create_post(async_client):
    await r.acheck_create(async_client, "/async/posts", {"title": "test_title"})


@pytest.mark.asyncio
async def test_create_fail(async_client):
    response = await async_client.post(
        "/async/posts",
        json={"id": "not_an_int"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_post(async_client, async_db):
    post = await Post(title="test").asave(async_db)
    await r.acheck_update(async_client, f"/async/posts/{post.id}", {"title": "aaa"})


@pytest.mark.asyncio
async def test_update_fail(async_client):
    response = await async_client.put(
        f"/async/posts/-1",
        json={"title": "asd"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_add_relationship(async_db, async_client):
    p, *_ = await mock_data(async_db)
    await r.acheck_update(
        async_client,
        f"/async/posts/{p.id}?include=messages",
        {"messages": [1, 2, 3]},
        expected_result={"id": p.id, "title": "post", "messages": [dict, dict, dict]},
    )


@pytest.mark.asyncio
async def test_update_scoped(async_db, async_client):
    p, *_ = await mock_data(async_db)
    response = await async_client.put(
        f"/async/posts/{p.id}/scopedput", json={"title": "new title"}
    )
    assert response.status_code == 404
    p = await Post.acreate(async_db, title="test1")
    response = await async_client.put(
        f"/async/posts/{p.id}/scopedput", json={"title": "new title"}
    )
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"id": p.id, "title": "new title"},
    )


@pytest.mark.asyncio
async def test_read_posts(async_client, async_db):
    posts = [await Post(title=f"test_{i}").asave(async_db) for i in range(10)]
    await r.acheck_filters(
        async_client, "/async/posts", {"title_like": "_1"}, {"title": "test_1"}
    )
    await r.acheck_filters(
        async_client,
        "/async/posts",
        {"ids": f"{posts[0].id},{posts[1].id}"},
        result_count=2,
    )
    await r.acheck_sort(async_client, "/async/posts")
    await r.acheck_pagination(async_client, "/async/posts", 10)


@pytest.mark.asyncio
async def test_read_post(async_client, async_db):
    post = await Post(title="test").asave(async_db)
    await r.acheck_read(async_client, "/async/posts", post.id)


@pytest.mark.asyncio
async def test_remove_post(async_client, async_db):
    post = await Post(id=1, title="test").asave(async_db)
    await r.acheck_delete(async_client, "/async/posts", 1)
    assert not await async_db.get(Post, 1)
