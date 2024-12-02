import pytest
from fastapi_solo import select
from fastapi_solo.aio import apaginate_query
from fastapi_solo.utils.testing import match
from tests.mock.models import Post


@pytest.mark.asyncio
async def test_paginate_query(async_db):
    p1 = await Post.acreate(async_db, title="post")
    await Post.acreate(async_db, title="post2")
    q = select(Post)
    p = await apaginate_query(async_db, q, 1, 1)
    assert match(
        p,
        {
            "data": [p1],
            "meta": {
                "currentPage": 1,
                "nextPage": 2,
                "pageSize": 1,
                "previousPage": None,
                "totalPages": 2,
                "total": 2,
            },
        },
    )


@pytest.mark.asyncio
async def test_paginate_query_all(async_db):
    p1 = await Post.acreate(async_db, title="post")
    p2 = await Post.acreate(async_db, title="post2")
    q = select(Post)
    p = await apaginate_query(async_db, q, 1, "all")
    assert match(
        p,
        {"data": [p1, p2]},
    )
