from fastapi_solo import Router
from example.models.tag import Tag
from example.schemas import tag as s

router = Router()

router.generate_crud(Tag, response_schema=s.Tag)
