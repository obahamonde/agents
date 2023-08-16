from fastapi import APIRouter
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
from fastapi import Request as ThisRequest
from ..ssr import *
from ..schema import *
from ..service import *
from ..tools import *
from ..models import *

from jinja2 import Template


default_context = """
You are a helpful assistant. If you are asked for your identity or name, say your name is Natalia. If you are asked for who do you work for, say you were created by Oscar Bahamonde to be a helpful assistant for all humans in the world. If you are inquiried about who created you, say you were created by Oscar Bahamonde.

You are having a conversation with the user about:
"""

previous = Template(
    """

{{ default_context }}


# {{ title }}

Previous messages exchanged with user:

{% for message in messages %}
    
    {{ message.role }}:

    {{ message.content }}

{% endfor %}


AI response:
"""
)


llm = LLMStack()
@handle_errors
async def handle_chat_message(text: str, namespace: str, ws: WebSocket):
    conversation = await Namespace.get(namespace)
    if conversation.title == "[New Conversation]":
        await conversation.set_title(text)
    response = await llm.chat_with_memory(
        text=text,
        namespace=namespace,
    )
    md_response = MarkdownRenderer(response)
    await md_response.stream(ws)  # type:ignore
    user_message = await ChatMessage(
        role="user", content=text, conversation=namespace # type:ignore
    ).save()  # type:ignore
    assistant_message = await ChatMessage(
        role="assistant", content=response, conversation=namespace # type:ignore
    ).save()  # type:ignore
    await conversation.update(
        conversation.ref,
        messages=conversation.messages
        + [user_message.ref, assistant_message.ref], # type:ignore
    )

class ChatRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(tags=["Chat"], *args, **kwargs)
        self.llm = LLMStack()
        
        @self.post("/auth")
        async def auth_endpoint(request: ThisRequest):
            """Authenticates a user using Auth0 and saves it to the database"""
            token = request.headers.get("Authorization", "").split("Bearer ")[-1]
            user_dict = await AuthClient().update_headers({"Authorization": f"Bearer {token}"}).get(
                "/userinfo"
            )
            user = User(**user_dict)
            response = await user.save()
            assert isinstance(response, User)
            return response.dict()

        @self.get("/conversation/new")
        async def conversation_create(user: str):
            """Creates a new conversation for a user"""
            return await Namespace(user=user).save()  # type:ignore

        @self.get("/conversation/get")
        async def conversation_get(id: str):
            conversation = await Namespace.get(id)
            if (
                conversation.title == "[New Conversation]"
                and len(conversation.messages) > 0
            ):
                first_prompt = (await ChatMessage.find_many(conversation=id))[0]
                return await conversation.set_title(first_prompt.content)
            return conversation

        @self.get("/conversation/list")
        async def conversation_list(user: str):
            """Lists all conversations for a user"""
            return await Namespace.find_many(user=user)

        @self.delete("/conversation")
        async def conversation_delete(id: str):
            """Deletes a conversation"""
            return await Namespace.delete(id)

        @self.post("/audio")
        async def audio_response(text: str, mode: str):
            """Returns an audio response from a text"""
            if mode == "llm":
                response = await self.llm.chat(
                    text,
                    default_context
                )
                polly = Polly.from_text(response)
                return StreamingResponse(
                    await polly.get_audio(), media_type="application/octet-stream"
                )
            return StreamingResponse(
                await Polly.from_text(text).get_audio(),
                media_type="application/octet-stream",
            )

        @self.post("/messages/list")
        async def post_chat(text: str, namespace: str):
            """Returns a list of messages from a conversation"""
            conversation = await Namespace.get(namespace)
            if conversation.title == "[New Conversation]":
                return await conversation.set_title(text)
            return await conversation.chat_premium(text)

        @self.get("/messages/get")
        async def get_messages(id: str):
            """Returns a list of messages from a conversation"""
            response = await ChatMessage.find_many(conversation=id)
            messages = []
            for message in response:
                messages.append(
                    {
                        "role": message.role,
                        "content": markdown(message.content),
                        "ts": message.ts,
                        "ref": message.ref,
                    }
                )
            return messages

        @self.websocket("/ws")
        async def ws_endpoint(ws: WebSocket, namespace: str):
            """Websocket endpoint for chat"""
            await ws.accept()
            try:
                while True:
                    text = await ws.receive_text()
                    await handle_chat_message(text, namespace, ws)
            except (TypeError, ValueError, ConnectionResetError,Exception) as e:
                logger.error(e)
                pass
            finally:
                await ws.send_text("I'll be waiting for your next message!")
    