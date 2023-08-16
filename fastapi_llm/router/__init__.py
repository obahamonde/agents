from .functions import *
from .knowledge import *
from .chat import *
from .content import *
from fastapi import APIRouter

class Router(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = "/api"
        self.include_router(ChatRouter())
        self.include_router(FunctionsRouter())
        self.include_router(KnowledgeRouter())
        self.include_router(ContentRouter())