import functools
from celery import Celery
from fastapi.responses import StreamingResponse

from ..config import env
from fastapi import APIRouter
from ..service import *
from ..schema import *
from ..tools import *

class FunctionsRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm = LLMStack()
        self.prefix = "/functions"
        self.tags =  ["Functions"]
        
        @self.get("/")
        async def functions_list():
            """
            Returns the functions catalog
            """
            return [f.openaischema for f in FunctionType.Metadata.subclasses]
        
        @self.worker.task
        async def automate(text: str, namespace: str)->None:
            """
            This function will be called by the publisher endpoint.
            It will call the function_call service and publish the response to the queue named `namespace`.
            """
            response = await function_call(
                text=text)
            queue = MessageQueue(namespace=namespace)
            await queue.pub(message=to_json(response))

        @self.get("/{namespace}")
        async def functions_consumer_endpoint(namespace: str):
            """
            # OpenAI Functions Consumer

            This endpoint is a streaming response that will return the results of the functions responses.
            The responses will be fetched from the queue named `namespace` and will be returned as a stream.
            The responses will be returned as a JSON object with the following structure:

            ```json
            {
                "name": "FunctionName",
                "data": "FunctionResponse"
            }
            ```

            You must implement your own error handling and retry logic.
            You must implement the functionality of each `FunctionType` tool by subclassing it and implementing the `run` method.
            """
            async def functions_consumer(ns: str):
                queue = MessageQueue(namespace=ns)
                async for message in queue.sub():
                    yield message
                    if message is not None:
                        await queue.ps.unsubscribe(ns)
                        break
                    else: 
                        await asyncio.sleep(2.5)
                    
            return StreamingResponse(functions_consumer(ns=namespace))

        @self.post("/{namespace}")
        async def functions_publisher_endpoint(text: str, namespace: str):
            """
            # OpenAI Functions Publisher

            This endpoint will publish a message to the queue named `namespace`.
            The parameters are:

            - `namespace`: The name of the queue to publish to

            - `text`: The text to send to the function

            You must implement your own error handling and retry logic.
            You must implement the functionality of each `FunctionType` tool by subclassing it and implementing the `run` method.

            """
            await automate(text=text, namespace=namespace)
            return {"message": f"Published to {namespace}"}

        @self.delete("/{namespace}")
        async def functions_unsuscribe_endpoint(namespace: str):
            """
            # OpenAI Functions Unsubscribe

            This endpoint will unsubscribe from the queue named `namespace`.
            The parameters are:

            - `namespace`: The name of the queue to unsubscribe from

            You must implement your own error handling and retry logic.
            You must implement the functionality of each `FunctionType` tool by subclassing it and implementing the `run` method.

            """
            queue = MessageQueue(namespace=namespace)
            await queue.ps.unsubscribe(namespace)
            return {"message": "Unsubscribed from queue."}

    @property
    def worker(self):
        return Celery(self.__class__.__name__, backend=env.REDIS_URL, broker=env.REDIS_URL)