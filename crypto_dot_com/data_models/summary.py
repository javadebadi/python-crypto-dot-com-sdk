"""Summary message  - not exactly the kind of data API returns"""

from pydantic import BaseModel


class UserBalanceSummary(BaseModel):
    currency: str
    market_value: float
    quantity: float
