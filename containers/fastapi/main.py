from typing import *

from aiofauna import APIServer
from aiofauna.openai import (
    Field,
    FunctionType,
    chat_completion,
    function_call,
    lang_chain,
    make_client,
)
from bs4 import BeautifulSoup

google = make_client(
    base_url="https://www.google.com",
    headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
    },
)
worldvectorlogos = make_client(
    base_url="https://worldvectorlogo.com",
    headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
    },
)


class Search(FunctionType):
    """
    Searches Google for a query
    """

    query: str
    lang: str = "en"
    limit: int = 10
    offset: int = 0

    async def run(self):
        text = await google.text(
            f"/search?q={self.query}&hl={self.lang}&num={self.limit}&start={self.offset}"
        )
        soup = BeautifulSoup(text, "html.parser")
        results = soup.find_all("div", class_="yuRUbf")
        return [i.a["href"] for i in results]


class ExtractLinks(FunctionType):
    """Extracts all links from a webpage"""

    url: str
    links: List[str] = Field(default_factory=list)

    async def run(self):
        text = await google.text(self.url)
        soup = BeautifulSoup(text, "html.parser")
        results = soup.find_all("a")
        links = [i["href"] for i in results]
        for link in links:
            if link.startswith("http"):
                self.links.extend(await ExtractLinks(url=link).run())
        return self.links


class Question(FunctionType):
    """
    Initiates a discussion between two large language models about a question
    """

    question: str
    iterations: int = 8

    async def run(self):
        return await lang_chain(self.question, iterations=self.iterations)


class SearchLogo(FunctionType):
    """
    Searches for a logo in worldvectorlogo
    """

    query: str
    offset: int = 0

    async def run(self):
        text = await worldvectorlogos.text(f"/search/{self.query}")
        soup = BeautifulSoup(text, "html.parser")
        results = soup.find_all("img", class_="logo__img")
        return [i["src"] for i in results]


async def pipeline(text: str):
    functions = [Question, Search, ExtractLinks, SearchLogo]
    return await function_call(text, functions)


app = APIServer()


@app.get("/")
async def index(text: str):
    return await pipeline(text)
