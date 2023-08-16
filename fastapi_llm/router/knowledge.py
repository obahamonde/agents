import functools
from celery import Celery
from fastapi.responses import StreamingResponse

from fastapi_llm.responses import EventSourceResponse
from ..config import env
from fastapi import APIRouter, File, UploadFile
from fastapi_llm.service import function_call
from ..service import *
from ..schema import *
from ..tools.loaders import website_loader, pdf_loader
from ..utils import chunker

class KnowledgeRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm = LLMStack()
        self.prefix = "/loaders"
        self.tags =  ["Loaders"]
    
        @self.post("/knowledge/pdf/{namespace}")
        async def pdf_loader_endpoint(namespace:str,file: UploadFile = File(...)):
            """Load a PDF file into the database"""
            async def generator():
                async for progress, text in pdf_loader(file):
                    await self.llm.ingest([text], namespace)
                    yield str(progress)
            return EventSourceResponse(generator())
        
        @self.post("/knowledge/website/{namespace}")
        async def website_loader_endpoint(namespace:str, url:str):
            """Load a website into the database"""
            async def generator():
                async for progress, text in website_loader(url):
                    await self.llm.ingest([text], namespace)
                    yield str(progress)
            return EventSourceResponse(generator())
                
        @self.get("/knowledge/{namespace}")
        async def knowledge_endpoint(text:str, namespace:str):
            """Get the knowledge graph for a namespace"""
            return await self.llm.chat_with_memory(text, namespace)