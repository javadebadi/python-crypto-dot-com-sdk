import datetime

from pydantic import BaseModel

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
