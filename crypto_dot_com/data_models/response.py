from pydantic import BaseModel


class CreateOrderDataMessage(BaseModel):
    client_oid: str
    order_id: str
