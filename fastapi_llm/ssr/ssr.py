import functools
from typing import Optional, AsyncGenerator
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import (
    TemplateAssertionError,
    TemplateError,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.rules_block import StateBlock
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import MarkdownLexer, get_lexer_by_name
from fastapi import HTTPException

from ..utils import setup_logging

EXCEPTIONS = (
    TemplateAssertionError,
    TemplateError,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
    Exception,
)

logger = setup_logging(__name__)


def handle_template(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except EXCEPTIONS as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    return wrapper


class HighlightRenderer(RendererHTML):
    def code_block(self, tokens, idx, options, env):
        token = tokens[idx]
        lexer = get_lexer_by_name(token.info.strip() if token.info else "text")
        formatter = HtmlFormatter()
        return highlight(token.content, lexer, formatter)


def highlight_code(code, name, attrs):
    """Highlight a block of code"""
    lexer = get_lexer_by_name(name)
    formatter = HtmlFormatter()

    return highlight(code, lexer, formatter)


class ServerSideRenderer(object):
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(["html", "xml", "jinja2", "md"]),
            enable_async=True,
        )
        self.md = MarkdownIt(
            "js-default",
            options_update={
                "html": True,
                "linkify": True,
                "typographer": True,
                "highlight": highlight_code,
            },
        )

    @handle_template
    async def render_markdown(self, template_name: str, **context) -> str:
        template = self.env.get_template(template_name)
        return self.md.render(await template.render_async(**context))

    @handle_template
    async def stream_markdown(
        self, template_name: str, **context
    ) -> AsyncGenerator[str, None]:
        template = self.env.get_template(template_name)
        async for chunk in template.generate_async(**context):
            yield self.md.render(chunk)

    @handle_template
    async def render_template(self, template_name: str, **context) -> str:
        template = self.env.get_template(template_name)
        return await template.render_async(**context)

    @handle_template
    async def stream_template(
        self, template_name: str, **context
    ) -> AsyncGenerator[str, None]:
        template = self.env.get_template(template_name)
        async for chunk in template.generate_async(**context):
            yield chunk

    @handle_template
    async def render_markdown_string(self, string: str):
        return self.md.render(string)

    @handle_template
    async def stream_markdown_string(self, string: str) -> AsyncGenerator[str, None]:
        for chunk in string:
            yield self.md.render(chunk)
