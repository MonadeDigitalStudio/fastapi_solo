from typing import Optional
from inflection import camelize
from ..utils.misc import log
from ..utils.config import FastapiSoloConfig


def check_filters(
    client, path: str, filters: dict, expected_result=None, result_count: int = 1
):
    """Test a given index endpoint to check if filters are working correctly."""
    query = "&".join([f"filter[{field}]={value}" for field, value in filters.items()])
    response = client.get(f"{path}?{query}")
    assert response.status_code == 200
    data = response.json().get("data")
    assert len(data) == result_count
    if expected_result:
        assert match(data[0], expected_result)

    return data


def check_sort(client, path: str, field: str = "id"):
    """Test a given index endpoint to check if sorting is working correctly."""
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
    """Test a given index endpoint to check if pagination is working correctly."""
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
    """Test a given show endpoint to check if reading by id is working correctly."""
    response = client.get(f"{path}{id}")
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
    """Test a given update endpoint to check if updating by id is working correctly."""
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
    """Test a given create endpoint to check if creating is working correctly."""
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
    """Test a given delete endpoint to check if deleting by id is working correctly."""
    if status_code is None:
        status_code = FastapiSoloConfig.delete_status_code
    response = client.delete(f"{path}{id}")
    assert response.status_code == status_code
    response = client.delete(f"{path}-1")
    assert response.status_code == 404


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
    """Check if data matches the given json."""
    if isinstance(data, dict) and isinstance(json, dict):
        return _match_dict(data, json)
    elif isinstance(data, list) and isinstance(json, list):
        return _match_list(data, json, check_array_length)
    elif isinstance(json, type):
        ret = isinstance(data, json)
        if not ret:
            log.error(f"Type {type(data)} does not match {json}")
        return ret
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
