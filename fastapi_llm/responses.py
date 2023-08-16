from fastapi.responses import *
from fastapi import *
from typing import AsyncGenerator


class EventSourceResponse(StreamingResponse):
    """Server Sent Events (SSE) response"""

    def __init__(self, generator: AsyncGenerator[str, None], **kwargs):
        super().__init__(
            generator,
            media_type="text/event-stream",
            **kwargs,
        )
