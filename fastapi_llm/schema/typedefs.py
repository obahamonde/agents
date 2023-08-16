from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    List,
    Type,
    TypeVar,
    Union,
    cast,
    Literal,
)
from uuid import UUID
from pydantic import Field
from pydantic import BaseConfig  # pylint: disable=no-name-in-module
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from pydantic import Extra  # pylint: disable=no-name-in-module
from pydantic.main import ModelMetaclass  # pylint: disable=no-name-in-module

from ..utils import handle_errors, process_time, setup_logging

Vector = List[float]
Value = str | int | float | bool | List[str]
MetaData = Dict[str, Value]
Filter = Literal["$eq", "$ne", "$lt", "$lte", "$gt", "$gte", "$in", "$nin"]
AndOr = Literal["$and", "$or"]
Query = Union[
    Dict[str, Union[Value, "Query", List[Value], List["Query"]]],
    Dict[AndOr, List[Dict[str, Union[Value, "Query", List[Value], List["Query"]]]]],
]
Size = Literal["256x256", "512x512", "1024x1024"]
Format = Literal["url", "b64_json"]

logger = setup_logging(__name__)


T = TypeVar("T")


class DocumentMeta(ModelMetaclass):
    """Metaclass for automatic generation of docstrings on Document classes and subclasses from their json schema"""

    def __new__(mcs, name, bases, namespace):
        new_cls = super().__new__(  # pylint:disable=too-many-function-args
            mcs, name, bases, namespace  # pylint:disable=too-many-function-args
        )  # pylint:disable=too-many-function-args
        if new_cls.__doc__ is None:
            new_cls.__doc__ = (
                """```json\n""" + new_cls.schema_json(indent=4) + """\n```"""
            )
        return new_cls


class Document(BaseModel, metaclass=DocumentMeta):  # pylint:disable=invalid-metaclass
    class Config(BaseConfig):
        """Config"""

        extra = Extra.allow
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.astimezone().isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
            timedelta: lambda v: v.total_seconds(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v),
            "Ref": lambda v: v.id(),
            "FaunaTime": lambda v: v.value,
            Enum: lambda v: v.value,
        }


D = TypeVar("D", bound=Document)


class LazyProxy(Generic[T], ABC):
    def __init__(self) -> None:
        self.__proxied: Union[T, None] = None

    def __getattr__(self, attr: str) -> object:
        return getattr(self.__get_proxied__(), attr)

    def __repr__(self) -> str:
        return repr(self.__get_proxied__())

    def __dir__(self) -> Iterable[str]:
        return self.__get_proxied__().__dir__()

    def __get_proxied__(self) -> T:
        proxied = self.__proxied

        if proxied is not None:
            return proxied

        self.__proxied = proxied = self.__load__()

        return proxied

    def __set_proxied__(self, value: T) -> None:
        self.__proxied = value

    def __as_proxied__(self) -> T:
        """Helper method that returns the current proxy, typed as the loaded object"""

        return cast(T, self)

    @abstractmethod
    def __load__(self) -> T:
        ...


class FunctionCall(Document):
    name: str
    data: Any


class FunctionType(BaseModel, ABC):
    class Metadata:
        subclasses: List[Type["FunctionType"]] = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        logger.debug("OpenAI Function %s called", self.__class__.__name__)

    @classmethod
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)

        _schema = cls.schema()
        logger.debug("OpenAI Function %s schema: %s", cls.__name__, _schema)
        if cls.__doc__ is None:
            raise ValueError(
                f"FunctionType subclass {cls.__name__} must have a docstring"
            )

        cls.openaischema = {
            "name": cls.__name__,
            "description": cls.__doc__,
            "parameters": {
                "type": "object",
                "properties": {
                    k: v for k, v in _schema["properties"].items() if k != "self"
                },
                "required": [k for k, v in _schema["properties"].items() if v],
            },
        }

        cls.Metadata.subclasses.append(cls)
        return cls

    @process_time
    @handle_errors
    async def __call__(self, **kwargs: Any) -> FunctionCall:
        response = await self.run(**kwargs)

        name = self.__class__.__name__
        logger.debug("OpenAI Function %s response: %s", name, response)
        return FunctionCall(name=name, data=response)

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        ...


F = TypeVar("F", bound=FunctionType)
