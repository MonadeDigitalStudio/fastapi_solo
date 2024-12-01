from typing import (
    TYPE_CHECKING,
    Callable,
    List,
    Type,
    Dict,
    Literal,
    TypeVar,
    Generic,
    Optional,
    Union,
    Any,
)
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel
from fastapi_solo.serialization.schemas import (
    CommonQueryParams,
    PaginationParams,
    IncludesParams,
    get_swagger_filters,
)
from fastapi_solo.utils.config import FastapiSoloConfig
from ..db.database import Session, Base, get_db, select, SelectModel
from ..utils.misc import VOID_CALLBACK
from ..utils.db import get_single_pk
from ..utils.pagination import paginate_query

T = TypeVar("T", bound=Base)
if TYPE_CHECKING:
    from ..serialization.schema_models import ResponseSchema, RequestSchema

BaseReq = Union[BaseModel, "ResponseSchema", "RequestSchema", Dict]


class Solo(Generic[T]):
    """Base class for solipsistic handlers

    properties:
    - db: the db session
    - includes: the includes from query params (except for delete)
    - filters: the filters from query params (only for index)
    - sort: the sort from query params (only for index)
    - page: the page from query params (only for index)
    - size: the size from query params (only for index)

    - query: the query object filtered, sorted and with includes, all from query params
    - base_query: the query object without filters, sort and includes

    methods:
    - execute: executes the query and returns the result to be rendered depending on the handler (index, show, create, update, delete)
    - query_one(:id)/get_element(:id): returns the query/element filtered by :id with includes from query params

    """

    db: Session
    includes: List[str] = []
    filters: Dict[str, str] = {}
    sort: List[str] = []
    page: int = 1
    size: int | Literal["all"]

    _model: T
    _base_query: Optional[SelectModel[T]] = None

    @property
    def base_query(self) -> SelectModel[T]:
        if self._base_query is None:
            return select(self._model)
        return self._base_query

    @property
    def query(self) -> SelectModel[T]:
        """Returns a query object filtered, sorted and with includes, all from query params"""
        return self.base_query.find(
            query_by=self.filters,
            sort=self.sort,
            include=self.includes,
        )

    def query_one(self, id):
        """Returns a query object filtered by id with includes from query params"""
        pk = get_single_pk(self._model)
        return self.base_query.includes(*self.includes).filter(pk == id)

    def get_element(self, id) -> Optional[T]:
        """Returns the element filtered by id with includes from query params"""
        return self.db.exec(self.query_one(id)).one_or_none()

    def execute(self, *args):
        """Executes the query and returns the result to be rendered depending on the handler (index, show, create, update, delete)"""
        raise NotImplementedError()

    def set_model(self, model: T):
        self._model = model

    def set_base_query(self, base_query: SelectModel[T]):
        self._base_query = base_query

    def paginate_query(
        self,
        q: SelectModel[T],
        page: Optional[int] = None,
        size: Optional[int] = None,
        before_render: Optional[Callable] = None,
    ):
        return paginate_query(
            self.db, q, page or self.page, size or self.size, before_render
        )


class Index(Solo[T]):
    def __init__(
        self,
        db: Session = Depends(get_db),
        params: CommonQueryParams = Depends(CommonQueryParams),
        pagination: PaginationParams = Depends(PaginationParams),
    ):
        self.db = db
        self.includes = params.includes
        self.filters = params.filters
        self.sort = params.sort
        self.page = pagination.page
        self.size: int | str = pagination.size

    def execute(self, paginate=True):
        """Executes the query (filtered, paginated and with includes) and returns the result in a dict for rendering the PaginatedResponse
        params:
        - paginate: if the result should be paginated or not

        returns:
        - a dict for rendering the PaginatedResponse
        """
        q = self.query
        if paginate:
            return paginate_query(self.db, q, self.page, self.size)
        return {"data": self.db.exec(q).all()}


class Show(Solo[T]):
    def __init__(
        self,
        db: Session = Depends(get_db),
        includes: IncludesParams = Depends(IncludesParams),
    ):
        self.db = db
        self.includes = includes

    def execute(self, id: Any) -> T:
        """Executes the query and returns the element by id
        params:
        - id: the id of the element to return

        returns:
        - the element by id
        """
        res = self.get_element(id)
        if not res:
            raise HTTPException(
                status_code=404, detail=f"{self._model.__name__} not found"
            )
        return res


class Create(Solo[T]):
    def __init__(
        self,
        response: Response,
        db: Session = Depends(get_db),
        includes: IncludesParams = Depends(IncludesParams),
    ):
        self.db = db
        self.includes = includes
        if not response.status_code:
            response.status_code = 201

    def execute(self, obj: BaseReq) -> T:
        """Executes the insert query
        params:
        - obj: the object to insert

        returns:
        - the created model
        """
        try:
            pk = get_single_pk(self._model)
            ret = self._model.create(self.db, obj)
            return self.get_element(getattr(ret, pk.name))  # type: ignore
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


class Update(Solo[T]):
    def __init__(
        self,
        db: Session = Depends(get_db),
        includes: IncludesParams = Depends(IncludesParams),
    ):
        self.db = db
        self.includes = includes

    def execute(self, id, obj: BaseReq) -> T:
        """Executes the update query
        params:
        - id: the id of the element to update
        - obj: the patch to apply to the element

        returns:
        - the updated model
        """
        m = self.get_element(id)
        if not m:
            raise HTTPException(
                status_code=404, detail=f"{self._model.__name__} not found"
            )
        try:
            return m.save(update=obj)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


class Delete(Solo[T]):
    def __init__(
        self,
        response: Response,
        db: Session = Depends(get_db),
    ):
        self.db = db
        if not response.status_code:
            response.status_code = FastapiSoloConfig.delete_status_code

    def execute(self, id):
        """Executes the delete query
        params:
        - id: the id of the element to delete
        """
        m = self.get_element(id)
        if not m:
            raise HTTPException(
                status_code=404, detail=f"{self._model.__name__} not found"
            )
        m.delete()


def get_solo(
    model: Base,
    solo_class: Type[Solo],
    get_query: Callable[..., SelectModel] = VOID_CALLBACK,
):
    if solo_class == Index and hasattr(model, "__queryable__"):
        swag = get_swagger_filters(model)
    else:
        swag = VOID_CALLBACK

    def _dep(
        solo: solo_class = Depends(solo_class),  # type: ignore
        base_query=Depends(get_query),
        _=Depends(swag),  # just to add the filters to the swagger docs to index
    ):
        solo.set_model(model)
        if base_query is not None:
            solo.set_base_query(base_query)
        return solo

    return _dep


def get_index(model: Base, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
    return get_solo(model, Index, get_query)


def get_show(model: Base, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
    return get_solo(model, Show, get_query)


def get_create(model: Base):
    return get_solo(model, Create)


def get_update(model: Base, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
    return get_solo(model, Update, get_query)


def get_delete(model: Base, get_query: Callable[..., SelectModel] = VOID_CALLBACK):
    return get_solo(model, Delete, get_query)
