"""API route definitions."""

from .chat import router as chat_router
from .discussions import router as discussions_router
from .hive import router as hive_router
from .attachments import router as attachments_router
from .projects import router as projects_router
from .templates import router as templates_router

__all__ = [
    "chat_router",
    "discussions_router",
    "hive_router",
    "attachments_router",
    "projects_router",
    "templates_router",
]
