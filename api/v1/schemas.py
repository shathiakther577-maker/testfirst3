from enum import Enum
from pydantic import BaseModel


class UserBalance(BaseModel):
    user_id: int
    balance: int


class TransactionType(Enum):
    IN = "in"
    OUT = "out"
    ALL = "all"


class Transaction(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    amount: int
    created_at: str


class SetCallback(BaseModel):
    callback_url: str
    callback_secret: str


class DropCallback(BaseModel):
    response: str = "ok"
