from fastapi import WebSocket
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from fastapi import WebSocket
from markdown_it.renderer import RendererHTML
from markdown_it import MarkdownIt


class MarkdownRenderer(object):
    def __init__(self, text, language=None):
        self.text = text
        self.language = language

    def format(self) -> str:
        if self.language:
            lexer = get_lexer_by_name(self.language)
        else:
            lexer = get_lexer_by_name("markdown")
        formatter = HtmlFormatter()
        return highlight(self.text, lexer, formatter)

    async def stream(self, websocket: WebSocket):
        await websocket.send_text(self.format())

def markdown(text: str):
    return MarkdownRenderer(text.strip()).format()



class HighlightRenderer(RendererHTML):
    def code_block(self, tokens, idx, options, env):
        token = tokens[idx]
        lexer = get_lexer_by_name(token.info.strip() if token.info else "markdown")
        formatter = HtmlFormatter()
        return highlight(token.content, lexer, formatter)


def highlight_code(code, name, attrs):
    """Highlight a block of code"""
    lexer = get_lexer_by_name(name)
    formatter = HtmlFormatter()

    return highlight(code, lexer, formatter)


md = MarkdownIt(
    "js-default",
    options_update={"html": True, "typographer": True, "highlight": highlight_code},
    renderer_cls=HighlightRenderer,
)


def render_markdown(text: str) -> str:
    """Render markdown to html"""
    return md.render(text.strip())
