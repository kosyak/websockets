from typing import NamedTuple

from .http11 import Request, Response


__all__ = [
    "Accept",
    "Connect",
    "Event",
    "Reject",
]


class Event:
    pass


class Connect(NamedTuple, Event):
    request: Request


class Accept(NamedTuple, Event):
    response: Response


class Reject(NamedTuple, Event):
    response: Response
    exception: Exception
