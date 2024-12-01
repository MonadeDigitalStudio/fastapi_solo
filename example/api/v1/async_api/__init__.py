from fastapi import APIRouter
from .posts import router as posts_router
from .messages import router as messages_router
from .tags import router as tags_router
from .polys import router as polys_router

router = APIRouter()

router.include_router(posts_router, prefix="/posts", tags=["posts"])
router.include_router(messages_router, prefix="/messages", tags=["messages"])
router.include_router(tags_router, prefix="/tags", tags=["tags"])
router.include_router(polys_router, prefix="/poly", tags=["poly"])
