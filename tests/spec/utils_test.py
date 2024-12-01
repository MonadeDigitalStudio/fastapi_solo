import logging
from fastapi_solo import select
from fastapi_solo.utils.misc import parse_bool
from fastapi_solo.utils.pagination import paginate_query, paginate_list, paginate_result
from fastapi_solo.utils.testing import match, validate_relationships
from tests.mock.models import Post, Base
from sqlalchemy.orm import relationship
import sqlalchemy as sa


def test_parse_bool():
    assert parse_bool("true") == True
    assert parse_bool("false") == False
    assert parse_bool("asd") is None
    assert parse_bool(True) == True
    assert parse_bool(False) == False


def test_paginate_query(db):
    p1 = Post.create(db, title="post")
    Post.create(db, title="post2")
    q = select(Post)
    p = paginate_query(db, q, 1, 1)
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


def test_paginate_query_all(db):
    p1 = Post.create(db, title="post")
    p2 = Post.create(db, title="post2")
    q = select(Post)
    p = paginate_query(db, q, 1, "all")
    assert match(
        p,
        {"data": [p1, p2]},
    )


def test_paginate_list(db):
    p1 = Post.create(db, title="post")
    p2 = Post.create(db, title="post2")
    p = paginate_list([p1, p2], 1, 1)
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


def test_paginate_result(db):
    p1 = Post.create(db, title="post")
    Post.create(db, title="post2")
    p = paginate_result([p1], 2, 1, 1)
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


def test_validate_relationships():
    assert validate_relationships(Post)
    assert validate_relationships("Message")
    assert validate_relationships("Tag")


def test_validate_relationships_without_relationships():
    class _Post2(Base):
        __tablename__ = "post2"
        id = sa.Column(sa.Integer, primary_key=True)

    assert validate_relationships(_Post2)


def test_validate_relationships_fail(caplog):
    class _Post3(Post):
        wrong = relationship("Tag")

    with caplog.at_level(logging.CRITICAL, logger="fastapi_solo"):
        assert not validate_relationships(_Post3)
