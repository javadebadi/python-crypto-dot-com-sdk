from pydantic import BaseModel

from crypto_dot_com.enums import OrderTypeEnum
from crypto_dot_com.enums import SideEnum


class CreateOrderMessage(BaseModel):
    pass


class CreateLimitOrderMessage(CreateOrderMessage):
    instrument_name: str
    quantity: str
    side: SideEnum
    price: str
    type: OrderTypeEnum = OrderTypeEnum["LIMIT"]
