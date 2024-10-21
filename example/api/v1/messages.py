from fastapi_solo import Router
from example.models.message import Message
from example.schemas import message as schema

router = Router()


router.generate_crud(
    Message,
    response_schema=schema.Message,
    create_schema=schema.MessageCreate,
    update_schema=schema.MessageUpdate,
)
