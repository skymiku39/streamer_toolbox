from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    module: str
    description: str
    kind: Literal["publisher", "subscriber"]


@dataclass(frozen=True)
class PublisherSpec(ProcessSpec):
    exchange: str


@dataclass(frozen=True)
class SubscriberSpec(ProcessSpec):
    exchange: str
    queue: str
