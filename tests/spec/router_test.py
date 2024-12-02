from fastapi_solo.utils.config import FastapiSoloConfig
from tests.mock.models import Post, Tag, Message
import fastapi_solo.utils.testing as r


def mock_data(db):
    p1 = Post(title="post").save(db)
    t1 = Tag(name="tag").save(db)
    t2 = Tag(name="tag2").save(db)
    m1 = Message(text="msg1", post_id=p1.id, tags=[t1, t2]).save(db)

    p2 = Post(title="post2").save(db)
    m2 = Message(text="msg2", post_id=p2.id, tags=[t1]).save(db)
    m3 = Message(text="msg3", post_id=p2.id, tags=[t2]).save(db)
    return (p1, p2, t1, t2, m1, m2, m3)


def test_get_one(db, client):
    mock_data(db)
    response = client.get("/posts/1")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"id": 1},
    )
    # test relationship after first level are not loaded
    assert response.json().get("messages") is None


def test_get_one_not_found(db, client):
    response = client.get("/posts/1")
    assert response.status_code == 404
    assert r.match(response.json(), {"detail": "Post not found"})


def test_get_one_with_includes(db, client):
    mock_data(db)
    response = client.get("/posts/1?include=messages.tags")

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


def test_get_one_without_includes(db, client):
    mock_data(db)
    response = client.get("/posts/1")

    assert response.status_code == 200

    json = response.json()
    assert r.match(
        json,
        {"id": 1},
    )
    assert not hasattr(json, "messages")


def test_get_one_with_2includes(db, client):
    mock_data(db)
    response = client.get("/messages/2?include=post.messages.tags")

    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "id": 2,
            "post": {
                "id": 2,
                "messages": [
                    {
                        "id": 2,
                        "tags": [{"id": 1}],
                    },
                    {
                        "id": 3,
                        "tags": [{"id": 2}],
                    },
                ],
            },
        },
    )


def test_get_all(db, client):
    mock_data(db)
    response = client.get("/posts?include=messages")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [
                {
                    "id": 1,
                    "messages": [
                        {
                            "id": 1,
                        },
                    ],
                },
                {
                    "id": 2,
                    "messages": [
                        {
                            "id": 2,
                        },
                        {
                            "id": 3,
                        },
                    ],
                },
            ],
            "meta": {
                "total": 2,
                "currentPage": 1,
                "totalPages": 1,
            },
        },
    )

    # test pagination
    response = client.get("/posts?page[size]=1")
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
    response = client.get("/posts?filter[title]=post2")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"data": [{"id": 2}]},
    )

    # test sort
    response = client.get("/posts?sort=-title")
    assert response.status_code == 200
    assert r.match(response.json(), {"data": [{"id": 2}, {"id": 1}]})

    # test includes
    response = client.get("/posts?include=messages.tags")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [
                {
                    "id": 1,
                    "messages": [
                        {
                            "id": 1,
                            "tags": [{"id": 1}, {"id": 2}],
                        },
                    ],
                },
                {
                    "id": 2,
                    "messages": [
                        {
                            "id": 2,
                            "tags": [{"id": 1}],
                        },
                        {
                            "id": 3,
                            "tags": [{"id": 2}],
                        },
                    ],
                },
            ],
        },
    )


def test_get_all_scoped(db, client):
    mock_data(db)
    response = client.get("/posts/scoped")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [],
        },
    )

    p = Post.create(db, title="test1")
    response = client.get("/posts/scoped")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [{"id": p.id}],
        },
    )


def test_get_all_scoped2(db, client):
    mock_data(db)
    response = client.get("/posts/scoped2")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {
            "data": [],
        },
    )


def test_create_post(client, db):
    r.check_create(client, "/posts", {"title": "test_title"})


def test_create_fail(client):
    response = client.post(
        "/posts/",
        json={"id": "not_an_int"},
    )
    assert response.status_code == 422


def test_update_post(client, db):
    post = Post(title="test").save(db)
    r.check_update(client, f"/posts/{post.id}", {"title": "aaa"})


def test_update_fail(client):
    response = client.put(
        f"/posts/-1",
        json={"title": "asd"},
    )
    assert response.status_code == 404


def test_update_remove_relationship(db, client):
    p, p2, t1, t2, m, *_ = mock_data(db)
    r.check_update(
        client,
        f"/messages/{m.id}",
        {"tags": []},
        expected_result={"id": m.id, "text": m.text, "tags": []},
    )


def test_update_add_relationship(db, client):
    p, *_ = mock_data(db)
    r.check_update(
        client,
        f"/posts/{p.id}",
        {"messages": [1, 2, 3]},
        expected_result={"id": p.id, "title": "post", "messages": [dict, dict, dict]},
    )


def test_update_scoped(db, client):
    p, *_ = mock_data(db)
    response = client.put(f"/posts/{p.id}/scopedput", json={"title": "new title"})
    assert response.status_code == 404
    p = Post.create(db, title="test1")
    response = client.put(f"/posts/{p.id}/scopedput", json={"title": "new title"})
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"id": p.id, "title": "new title"},
    )


def test_update_scoped2(db, client):
    p, *_ = mock_data(db)
    response = client.put(f"/posts/{p.id}/scopedput2", json={"title": "new title"})
    assert response.status_code == 404


def test_read_posts(client, db):
    posts = [Post(title=f"test_{i}").save(db) for i in range(10)]
    r.check_filters(client, "/posts", {"title_like": "_1"}, {"title": "test_1"})
    r.check_filters(
        client, "/posts", {"ids": f"{posts[0].id},{posts[1].id}"}, result_count=2
    )
    r.check_sort(client, "/posts")
    r.check_pagination(client, "/posts", 10)


def test_read_post(client, db):
    post = Post(title="test").save(db)
    r.check_read(client, "/posts", post.id)


def test_read_post_scoped(client, db):
    p, *_ = mock_data(db)
    response = client.get(f"/posts/{p.id}/scoped")
    assert response.status_code == 404
    p = Post.create(db, title="test1")
    response = client.get(f"/posts/{p.id}/scoped")
    assert response.status_code == 200
    assert r.match(
        response.json(),
        {"id": p.id, "title": "test1"},
    )


def test_read_post_scoped2(client, db):
    p, *_ = mock_data(db)
    response = client.get(f"/posts/{p.id}/scoped2")
    assert response.status_code == 404


def test_remove_post(client, db):
    post = Post(title="test").save(db)
    r.check_delete(client, "/posts", post.id)
    assert not db.get(Post, post.id)


def test_remove_post_scoped(client, db):
    p, *_ = mock_data(db)
    response = client.delete(f"/posts/{p.id}/scopeddelete")
    assert response.status_code == 404
    p = Post.create(db, title="test1")
    response = client.delete(f"/posts/{p.id}/scopeddelete")
    assert response.status_code == FastapiSoloConfig.delete_status_code


def test_remove_post_scoped2(client, db):
    p, *_ = mock_data(db)
    response = client.delete(f"/posts/{p.id}/scopeddelete2")
    assert response.status_code == 404
