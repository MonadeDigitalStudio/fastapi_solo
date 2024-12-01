"""
.. include:: ../README.md
"""

from .db import (
    SessionFactory as SessionFactory,
    Base as Base,
    BaseWithTS as BaseWithTS,
    get_raw_session as get_raw_session,
    get_db as get_db,
    Session as Session,
    Transaction as Transaction,
    get_root_transaction as get_root_transaction,
    QueryModel as QueryModel,
    SelectModel as SelectModel,
    select as select,
    queryable as queryable,
)

from .router import (
    Router as Router,
    Solo as Solo,
)

from .serialization.schemas import (
    all_optional as all_optional,
    BaseSchema as BaseSchema,
    PaginationMeta as PaginationMeta,
    PaginatedResponse as PaginatedResponse,
    PaginationParams as PaginationParams,
    IncludesParams as IncludesParams,
    FiltersParams as FiltersParams,
    SortParams as SortParams,
    CommonQueryParams as CommonQueryParams,
    DateTime as DateTime,
    lazy_validator as lazy_validator,
    HasOne as HasOne,
    HasMany as HasMany,
    get_swagger_filters as get_swagger_filters,
)
from .serialization.schema_models import (
    response_schema as response_schema,
    request_schema as request_schema,
    ResponseSchema as ResponseSchema,
    RequestSchema as RequestSchema,
)

from .utils.config import FastapiSoloConfig as FastapiSoloConfig

from .utils.inject import injector as injector

from .utils.pagination import (
    paginate_query as paginate_query,
    paginate_result as paginate_result,
    paginate_list as paginate_list,
)

from .dependencies import (
    SessionDep as SessionDep,
    RootTransactionDep as RootTransactionDep,
    IndexDep as IndexDep,
    ShowDep as ShowDep,
    CreateDep as CreateDep,
    UpdateDep as UpdateDep,
    DeleteDep as DeleteDep,
)
