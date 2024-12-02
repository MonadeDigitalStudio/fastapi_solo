from typing import Optional, Type, overload
from types import UnionType
from inflection import camelize

from fastapi_solo.db.database import Base
from sqlalchemy.orm import RelationshipProperty
from ..utils.misc import log
from ..utils.config import FastapiSoloConfig


def check_filters(
    client, path: str, filters: dict, expected_result=None, result_count: int = 1
):
    """
    Test a given index endpoint to check if filters are working correctly.

    Parameters:
    - client: the test client
    - path: the path to the index endpoint
    - filters: the filters to apply
    - expected_result: the expected result to match, optional
    - result_count: the expected result count, default 1

    Returns:
    - the data from the response

    Example:
    - check_filters(client, "/posts", {"title": "Hello, world!"}, {"title": "Hello, world!"})
    """
    query = "&".join([f"filter[{field}]={value}" for field, value in filters.items()])
    response = client.get(f"{path}?{query}")
    assert response.status_code == 200
    data = response.json().get("data")
    assert len(data) == result_count
    if expected_result:
        assert match(data[0], expected_result)

    return data


def check_sort(client, path: str, field: str = "id"):
    """
    Test a given index endpoint to check if sorting is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the index endpoint
    - field: the field to sort by, default "id"

    Returns:
    - the data from the response

    Example:
    - check_sort(client, "/posts", "title")
    """
    response = client.get(f"{path}?sort={field}")
    data = response.json().get("data")
    assert response.status_code == 200
    ids = [obj[camelize(field, False)] for obj in data]
    assert ids == sorted(ids)

    response = client.get(f"{path}?sort=-{field}")
    data = response.json().get("data")
    assert response.status_code == 200
    ids = [obj[camelize(field, False)] for obj in data]
    assert ids == sorted(ids, reverse=True)

    return data


def check_pagination(client, path: str, total: int, page_size: int = 2):
    """
    Test a given index endpoint to check if pagination is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the index endpoint
    - total: the total number of elements
    - page_size: the page size, default 2

    Returns:
    - the data and meta from the response

    Example:
    - check_pagination(client, "/posts")
    """
    assert total >= page_size * 2

    response = client.get(f"{path}?page[number]=1&page[size]={page_size}")
    body = response.json()
    data = body.get("data")
    meta = body.get("meta")
    total_pages = (total // page_size) + 1
    if total % page_size == 0:
        total_pages -= 1

    assert response.status_code == 200
    assert len(data) == page_size
    assert meta["totalPages"] == total_pages
    assert meta["currentPage"] == 1
    assert meta["nextPage"] == 2
    assert meta["previousPage"] is None

    response = client.get(f"{path}?page[number]={total_pages}&page[size]={page_size}")
    body = response.json()
    data = body.get("data")
    meta = body.get("meta")
    assert response.status_code == 200
    assert len(data) == total % page_size or page_size
    assert meta["totalPages"] == total_pages
    assert meta["currentPage"] == total_pages
    assert meta["nextPage"] is None
    assert meta["previousPage"] == total_pages - 1

    response = client.get(f"{path}?page[number]={total_pages+1}&page[size]={page_size}")
    body = response.json()
    data = body.get("data")
    meta = body.get("meta")
    assert response.status_code == 200
    assert len(data) == 0
    assert meta["totalPages"] == total_pages
    assert meta["currentPage"] == total_pages + 1
    assert meta["nextPage"] is None
    assert meta["previousPage"] == total_pages

    return data, meta


def check_read(client, path: str, id, pk: str = "id", expected_result=None):
    """
    Test a given show endpoint to check if reading by id is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the show endpoint
    - id: the id to read
    - pk: the primary key, default "id"
    - expected_result: the expected result to match, optional

    Returns:
    - the data from the response

    Example:
    - check_read(client, "/posts", 1, "id", {"id": int})
    """
    response = client.get(f"{path}/{id}")
    assert response.status_code == 200
    assert response.json()[pk] == id
    response = client.get(f"{path}-1")
    assert response.status_code == 404

    result = response.json()
    if expected_result:
        assert match(result, expected_result)
    return result


def check_update(
    client,
    path: str,
    json: Optional[dict] = None,
    data=None,
    status_code: int = 200,
    expected_result=None,
):
    """
    Test a given update endpoint to check if updating by id is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the update endpoint
    - json: the json payload to send
    - data: the payload to send (alternative to json)
    - status_code: the expected status code, default 200
    - expected_result: the expected result to match, optional
    """
    return _check_save(
        client.put,
        path,
        json=json,
        data=data,
        status_code=status_code,
        expected_result=expected_result,
    )


def check_create(
    client,
    path: str,
    json: Optional[dict] = None,
    data=None,
    status_code: int = 201,
    expected_result=None,
):
    """
    Test a given create endpoint to check if creating is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the create endpoint
    - json: the json payload to send
    - data: the payload to send (alternative to json)
    - status_code: the expected status code, default 201
    - expected_result: the expected result to match, optional

    Returns:
    - the data from the response

    Example:
    - check_create(client, "/posts", {"title": "Hello, world!"}, {"title": "Hello, world!"})
    """
    return _check_save(
        client.post,
        path,
        json=json,
        data=data,
        status_code=status_code,
        expected_result=expected_result,
    )


def _check_save(
    fn,
    path: str,
    json: Optional[dict],
    status_code: int,
    data,
    expected_result,
):
    response = fn(path, json=json, data=data)

    assert response.status_code == status_code
    body = response.json()
    assert match(body, expected_result or json or data)
    return body


def check_delete(client, path: str, id, status_code: Optional[int] = None):
    """
    Test a given delete endpoint to check if deleting by id is working correctly.

    Parameters:
    - client: the test client
    - path: the path to the delete endpoint
    - id: the id to delete
    - status_code: the expected status code, default 204 (configurable in FastapiSoloConfig)
    """
    if status_code is None:
        status_code = FastapiSoloConfig.delete_status_code
    response = client.delete(f"{path}/{id}")
    assert response.status_code == status_code
    response = client.delete(f"{path}-1")
    assert response.status_code == 404


class ListOfElements:
    """A helper class to match a list of elements with match function. Example: ListOfElements(int). Alternatively, use a_list_of."""

    def __init__(self, struct) -> None:
        self.struct = struct


def a_list_of(struct):
    """A helper function to match a list of elements with match function. Example: a_list_of(int)"""
    return ListOfElements(struct)


def _match_dict(data, json):
    for key, value in json.items():
        if key not in data.keys():
            log.error(f"Key {key} not found in data:\n{data}")
            return False
        if not match(data[key], value):
            log.error(f"Value {data[key]} does not match {value}")
            return False
    return True


def _match_list(data, json, check_array_length=True):
    if check_array_length and len(data) != len(json):
        log.error(f"Array length {len(data)} does not match {len(json)}")
        return False
    for i in range(len(json)):
        if not match(data[i], json[i]):
            log.error(f"Element {data[i]} does not match {json[i]}")
            return False
    return True


def match(data, json, check_array_length=True):
    """
    Check if data matches the given json.

    Parameters:
    - data: the data to check
    - json: the json structure to match
    - check_array_length: if the length of arrays should be checked

    Returns:
    - True if data matches the json, False otherwise

    Example:
    - match({"a": 1}, {"a": 1}) -> True
    - match([1, 2, 3], a_list_of(int)) -> True
    - match({"a": 1, "b": [1, 2, 3]}, {"a": int, "b": a_list_of(int)}) -> True
    """
    if isinstance(data, dict) and isinstance(json, dict):
        return _match_dict(data, json)
    elif isinstance(data, list) and isinstance(json, list):
        return _match_list(data, json, check_array_length)
    elif isinstance(json, ListOfElements):
        return all(match(elem, json.struct) for elem in data)
    elif isinstance(json, type):
        ret = isinstance(data, json)
        if not ret:
            log.error(f"Type {type(data)} does not match {json}")
        return ret
    elif isinstance(json, UnionType):
        return any(match(data, elem) for elem in json.__args__)
    elif hasattr(json, "__origin__"):
        ret = isinstance(data, json.__origin__)
        if not ret:
            log.error(f"Type {type(data)} does not match {json}")
        return ret
    else:
        ret = data == json
        if not ret:
            log.error(f"Value {data} does not match {json}")
        return ret


def _validate_relationship(model, prop):
    if not getattr(prop, "back_populates", None):
        log.error(
            f"Relationship {prop.key} in {model} does not have reverse relationship"
        )
        return False
    rel_model = prop.mapper.class_
    back_populates = prop.back_populates
    if not getattr(rel_model, back_populates, None):
        log.error(
            f"Reverse relationship {back_populates} in {rel_model} does not exist"
        )
        return False
    rel_field = rel_model.__mapper__.get_property(back_populates)
    if not isinstance(rel_field, RelationshipProperty):
        log.error(
            f"Reverse relationship {back_populates} in {rel_model} is not a relationship"
        )
        return False
    rel_back_populates = rel_field.back_populates
    if not rel_back_populates or rel_back_populates != prop.key:
        log.error(
            f"Reverse relationship {back_populates} in {rel_model} does not match {prop.key}"
        )
        return False
    return True


@overload
def validate_relationships(model: str): ...


@overload
def validate_relationships(model: Type[Base]): ...


def validate_relationships(model):
    """
    Validate relationships in a model.

    Parameters:
    - model: the model to validate

    Returns:
    - True if the model is valid, False otherwise

    Example:
    - assert validate_relationships(Post)
    """

    if isinstance(model, str):
        model = Base.get_model(model)

    for prop in model.__mapper__.iterate_properties:
        if isinstance(prop, RelationshipProperty) and not _validate_relationship(
            model, prop
        ):
            return False
    return True
