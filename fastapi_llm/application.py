from .main import *
from .schema import *
from .service import *
from .tools import *
from .responses import *
from .router import *

class AgentsAPI(FastAPI):
    """
    FastAPI with LLM extensions
    """
    def __init__(self, **kwargs):
        if self.__class__.__doc__ is None:
            self.__class__.__doc__ = "Intelligent Agents API"
        super().__init__(title=self.__class__.__name__, description=self.__class__.__doc__, version="0.1.0", **kwargs)
        
        self.llm = LLMStack()
        
        @self.on_event("startup")
        async def startup():
            await FaunaModel.create_all()

        @self.on_event("shutdown")
        async def shutdown():
            await APIClient.cleanup()
            
        self.include_router(Router())
        