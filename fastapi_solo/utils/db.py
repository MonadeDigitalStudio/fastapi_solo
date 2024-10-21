import datetime
from sys import version_info
from sqlalchemy import DateTime, func
from sqlalchemy.orm import MappedColumn
from ..exc import DbException

if version_info.minor >= 12:

    def utcnow():
        return datetime.datetime.now(datetime.UTC)

else:
    utcnow = datetime.datetime.utcnow

CreatedAtColumn = MappedColumn(
    "created_at",
    DateTime,
    nullable=False,
    default=utcnow,
    server_default=func.now(),
)

UpdatedAtColumn = MappedColumn(
    "updated_at",
    DateTime,
    nullable=False,
    default=utcnow,
    onupdate=utcnow,
    server_default=func.now(),
)

timestamps = [
    CreatedAtColumn,
    UpdatedAtColumn,
]


def get_single_pk(model):
    pk = model.__mapper__.primary_key
    if len(pk) > 1:
        raise DbException("Composite primary key not supported")
    return pk[0]
