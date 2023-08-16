"""Logging and error handling utilities for the OpenAI Function Python package."""
import functools
import os
import shutil
import socket
import subprocess
import asyncio
import functools
import logging
from time import perf_counter
from typing import Any, Callable, Coroutine, TypeVar, cast, Sequence, Iterable
from concurrent.futures import ProcessPoolExecutor
from aiohttp.web_exceptions import HTTPException
from rich.console import Console
from rich.logging import RichHandler
from rich.pretty import install
from rich.traceback import install as ins
from jinja2 import Template

T = TypeVar("T")


def setup_logging(name: str) -> logging.Logger:
    """
    Set's up logging using the Rich library for pretty and informative terminal logs.

    Arguments:
    name -- Name for the logger instance. It's best practice to use the name of the module where logger is defined. # pylint: disable=line-too-long
    """
    install()
    ins()
    console = Console(record=True, force_terminal=True)
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_extra_lines=2,
        tracebacks_theme="monokai",
        show_level=False,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG, handlers=[console_handler])
    logger_ = logging.getLogger(name)
    logger_.setLevel(logging.DEBUG)
    return logger_


logger = setup_logging(__name__)


def process_time(
    func: Callable[..., Coroutine[Any, Any, T]]
) -> Callable[..., Coroutine[Any, Any, T]]:  # pylint: disable=line-too-long
    """
    A decorator to measure the execution time of an asynchronous function.

    Arguments:
    func -- The asynchronous function whose execution time is to be measured.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """
        Wrapper function to time the function call.
        """
        start = perf_counter()
        result = await func(*args, **kwargs)
        end = perf_counter()
        logger.info("Time taken to execute %s: %s seconds", func.__name__, end - start)
        return result

    return wrapper


def handle_errors(
    func: Callable[..., Coroutine[Any, Any, T]]
) -> Callable[..., Coroutine[Any, Any, T]]:  # pylint: disable=line-too-long
    """
    A decorator to handle errors in an asynchronous function.

    Arguments:
    func -- The asynchronous function whose errors are to be handled.
    """

    async def wrapper(*args: Any, **kwargs: Any) -> T:
        """
        Wrapper function to handle errors in the function call.
        """
        try:
            logger.info("Calling %s", func.__name__)
            return await func(*args, **kwargs)
        except HTTPException as exc:
            logger.error(exc.__class__.__name__)
            logger.error(exc.reason)
            raise exc from exc
        except Exception as exc:
            logger.error(exc.__class__.__name__)
            logger.error(str(exc))
            raise exc from exc

    return wrapper


def chunker(seq: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))


def gen_emptystr() -> str:
    return cast(str, None)


nginx_template = Template(
    """
    server {
    listen 80;
    server_name {{ name }}.aiofauna.com;

    location / {
        proxy_pass http://localhost:{{ port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }

    location /api/sse {
        proxy_pass http://localhost:{{ port }};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        proxy_ignore_headers "Cache-Control" "Expires";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://localhost:{{ port }};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
)


def nginx_cleanup():
    directories = [
        "/etc/nginx/conf.d",
        "/etc/nginx/sites-enabled",
        "/etc/nginx/sites-available",
    ]

    for directory in directories:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    print(f"Deleted {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")


def nginx_render(name: str, port: int):
    """Render nginx configuration"""
    for path in [
        "/etc/nginx/conf.d",
        "/etc/nginx/sites-enabled",
        "/etc/nginx/sites-available",
    ]:
        os.makedirs(path, exist_ok=True)
        with open(f"./src/templates/{path}/{name}.conf", "w", encoding="utf-8") as f:
            f.write(nginx_template.render(name=name, port=port))

    subprocess.run(["nginx", "-s", "reload"])


def gen_port():
    """Generate a random port"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def async_io(func: Callable[[Any], T]) -> Callable[..., Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await asyncio.to_thread(func, *args, **kwargs)

    return wrapper


def async_cpu(func: Callable[[Any], T]) -> Callable[..., Coroutine[Any, Any, T]]:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        with ProcessPoolExecutor() as pool:
            return await asyncio.get_running_loop().run_in_executor(
                pool, func, *args, **kwargs
            )

    return wrapper
