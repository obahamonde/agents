import asyncio

import aiohttp
from ..schema.typedefs import *
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from typing import Optional

class SearchResult(Document):
    title: str = Field(...)
    url: str = Field(...)


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/90.0.4430.212 Chrome/90.0.4430.212 Safari/537.36"
}

SEO_DATA = {
    "description": "",
    "keywords": "",
    "og:title": "",
    "og:description": "",
    "og:image": "",
    "og:url": "",
    "twitter:card": "",
    "twitter:title": "",
    "twitter:description": "",
    "twitter:image": "",
}


async def search_google(
    text: str, lang: str = "en", limit: int = 10
) -> List[SearchResult]:
    async with ClientSession(headers=BROWSER_HEADERS) as session:
        async with session.get(
            f"https://www.google.com/search?q={text}&hl={lang}&num={limit}"
        ) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")
            results = soup.find_all("div", attrs={"class": "yuRUbf"})
            return [
                SearchResult(
                    title=result.find("h3").text, url=result.find("a").get("href")
                )
                for result in results
            ]


async def get_seo_data(url: str, session: ClientSession):
    async with session.get(url) as response:
        seo_data = SEO_DATA.copy()
        soup = BeautifulSoup(await response.text(), "html.parser")
        for meta_tag in soup.find_all("meta"):
            if tag_name := meta_tag.get("name", meta_tag.get("property")):
                if tag_name.lower() in seo_data:
                    seo_data[tag_name.lower()] = meta_tag.get("content", "")
            if not (seo_data["og:title"] or seo_data["twitter:title"]) and (
                title_tag := soup.find("title")
            ):
                seo_data["title"] = title_tag.text
        return seo_data


class SEOTags(FunctionType):
    """
    Searches for most used SEO Keywords on top ranked websites.
    """

    query: str = Field(...)
    lang: str = Field(default="en")
    limit: int = Field(default=10)
    results: Optional[List[SearchResult]] = Field(default=None)

    async def run(self):
        self.results = await search_google(self.query, self.lang, self.limit)
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS) as session:
            tasks = [get_seo_data(result.url, session) for result in self.results]
            self.results = await asyncio.gather(*tasks)
        return self.results


class GoogleSearch(FunctionType):
    """
    Searches for content in google, intended for helping users search content not available on the knowledge base.
    """

    query: str = Field(...)
    lang: str = Field(default="en")
    limit: int = Field(default=10)
    results: Optional[List[SearchResult]] = Field(default=None)

    async def run(self):
        self.results = await search_google(self.query, self.lang, self.limit)
        return self.results
