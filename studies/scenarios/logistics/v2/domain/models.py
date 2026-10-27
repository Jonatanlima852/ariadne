"""Structured contracts shared by the scenario agents."""
from typing import Literal
from pydantic import BaseModel


class Item(BaseModel):
    sku: str
    quantity: int


class Order(BaseModel):
    id: str
    destination: str
    items: list[Item]
    priority: int
    deadline: int


class Requirements(BaseModel):
    orders: list[Order]


class Dependency(BaseModel):
    task: str
    requires: list[str]


class Mission(BaseModel):
    order_ids: list[str]
    dependencies: list[Dependency]
    explanation: str


class Analysis(BaseModel):
    affected_orders: list[str]
    review: list[Literal['inventory', 'resource', 'route', 'energy']]
    explanation: str


class Report(BaseModel):
    explanation: str


class Action(BaseModel):
    type: Literal['MOVE', 'LOAD', 'TRANSFER', 'RECHARGE', 'DELIVER']
    vehicle: str
    origin: str | None
    destination: str | None
    order: str | None
    depot: str | None
    source_vehicle: str | None


class Proposal(BaseModel):
    actions: list[Action]
    explanation: str


def action_mapper(parsed):
    actions = []
    for a in parsed.actions:
        value = a.model_dump(exclude_none=True)
        if 'origin' in value:
            value['from'] = value.pop('origin')
        if 'destination' in value:
            value['to'] = value.pop('destination')
        actions.append(value)
    return {'actions': actions, 'explanation': parsed.explanation}
