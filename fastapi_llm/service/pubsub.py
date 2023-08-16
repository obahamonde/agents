from typing import AsyncGenerator, TypeVar

import aioredis
from .faunadb.json import to_json
from .openai import function_call
from ..schema import *
from ..tools import *
from ..utils import handle_errors, setup_logging
from aioredis.client import PubSub

from ..config import env

logger = setup_logging(__name__)

pool = aioredis.Redis.from_url(env.REDIS_URL)

EXCEPTIONS =  (KeyError, AssertionError, UnicodeDecodeError, AttributeError)

class MessageQueue(LazyProxy[PubSub]):
    def __init__(self, namespace: str):
        """Initializes a new FunctionQueue Event Stream to catch function call event results in an asynchronous fashion."""
        self.namespace = namespace
        logger.info(f"Initializing state for {namespace}")
        self.ps = self.__load__()

    def __load__(self):
        """Lazy loading of the PubSub object."""
        return pool.pubsub()

    async def sub(self) -> AsyncGenerator[str, None]:
        """Subscribes to the PubSub channel and yields messages as they come in."""
        await self.ps.subscribe(self.namespace)
        logger.info("Subscribed to %s", self.namespace)
        async for message in self.ps.listen():
            try:
                data = message["data"]
                yield data.decode("utf-8")
            except EXCEPTIONS:
                logger.error("Invalid message received %s", message)
                continue

    @handle_errors
    async def _send(self, message: str) -> None:
        """Protected method to send a message to the PubSub channel."""
        logger.info(f"Sending message to {self.namespace}")
        await pool.publish(self.namespace, message)

    @handle_errors
    async def pub(self, message: str) -> None:
        """Public method to send a function call result to the PubSub channel."""
        try:
            response = await function_call(
                text=message,
                context="You are a function Orchestrator",
                model="gpt-3.5-turbo-16k-0613"
            )
            logger.info(f"Message sent to {self.namespace}")
            return await self._send(to_json(response))
        except EXCEPTIONS:
            logger.error(f"Invalid message received {message}")
            return await self._send("Invalid message received")
        finally:
            await self.ps.unsubscribe(self.namespace)