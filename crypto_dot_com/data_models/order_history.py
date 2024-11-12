import datetime
import json

from pydantic import BaseModel
from pydantic import field_validator

from crypto_dot_com.enums import ExecInstEnum
from crypto_dot_com.enums import OrderTypeEnum
from crypto_dot_com.enums import SideEnum
from crypto_dot_com.enums import StatusEnum
from crypto_dot_com.enums import TimeInForceEnum


class OrderHistoryDataMessage(BaseModel):
    account_id: str
    order_id: str
    client_oid: str
    order_type: OrderTypeEnum
    time_in_force: TimeInForceEnum
    side: SideEnum
    exec_inst: list[ExecInstEnum]
    quantity: float
    order_value: float
    maker_fee_rate: float | None = None
    taker_fee_rate: float | None = None
    avg_price: float
    ref_price: float
    ref_price_type: str | None = None
    cumulative_quantity: float
    cumulative_value: float
    cumulative_fee: float
    status: StatusEnum
    update_user_id: str
    order_date: datetime.date
    instrument_name: str
    fee_instrument_name: str
    reason: int
    create_time: int  # ms
    create_time_ns: float
    update_time: int  # ms
    limit_price: float | None = None

    @field_validator("exec_inst", mode="before")
    def parse_exec_inst(cls, value: str | list[str]) -> list[str]:
        # Check if the value is a string that looks like a list
        if isinstance(value, str):
            try:
                # Attempt to parse the string as JSON
                return [ExecInstEnum(value) for value in json.loads(value)]
            except json.JSONDecodeError:
                raise ValueError(
                    "exec_inst must be a valid JSON list of strings"
                )
        return value  # If already a list, return as is
