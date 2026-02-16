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

tznow = lambda: datetime.datetime.now().astimezone()

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

CreatedAtTZColumn = MappedColumn(
    "created_at",
    DateTime(timezone=True),
    nullable=False,
    default=tznow,
    server_default=func.now(),
)

UpdatedAtTZColumn = MappedColumn(
    "updated_at",
    DateTime(timezone=True),
    nullable=False,
    default=tznow,
    onupdate=tznow,
    server_default=func.now(),
)

timestamps = [
    CreatedAtColumn,
    UpdatedAtColumn,
]

timestamps_tz = [
    CreatedAtTZColumn,
    UpdatedAtTZColumn,
]


def get_single_pk(model):
    pk = model.__mapper__.primary_key
    if len(pk) > 1:
        raise DbException("Composite primary key not supported")
    return pk[0]
