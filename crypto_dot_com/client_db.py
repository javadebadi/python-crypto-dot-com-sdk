import datetime
from typing import Any
from typing import cast

import pytz
from xarizmi.candlestick import Candlestick
from xarizmi.candlestick import CandlestickChart
from xarizmi.config import get_config
from xarizmi.db.actions.candlestick import get_filtered_candlesticks
from xarizmi.db.actions.candlestick import upsert_candlestick
from xarizmi.db.actions.exchange import upsert_exchange
from xarizmi.db.actions.order import delete_all_cancelled_orders
from xarizmi.db.actions.order import get_active_orders
from xarizmi.db.actions.order import upsert_order
from xarizmi.db.actions.portfolio import bulk_upsert_portfolio_item
from xarizmi.db.actions.portfolio.portfolio_read import (
    get_portfolio_items_between_dates,
)
from xarizmi.db.actions.symbol import get_symbol
from xarizmi.db.actions.symbol import upsert_symbol
from xarizmi.db.admin import run_db_migration
from xarizmi.db.client import session_scope
from xarizmi.db.models.candlestick import CandleStick as DbCandlestick
from xarizmi.enums import IntervalTypeEnum
from xarizmi.models.orders import Order
from xarizmi.models.portfolio import Portfolio
from xarizmi.models.symbol import Symbol

from .client import CryptoAPI
from .client import get_xarizmi_symbol_from_instrument_name
from .enums import CandlestickTimeInterval
from .settings import EXCHANGE
from .settings import EXCHANGE_NAME


class CryptoDbApiClient(CryptoAPI):

    def __init__(
        self,
        database_url: str,
        api_key: str,
        api_secret: str,
        timeout: int = 1000,
        log_json_response_to_file: bool = False,
        logs_directory: str | None = None,
    ) -> None:
        super().__init__(
            api_key,
            api_secret,
            timeout,
            log_json_response_to_file,
            logs_directory,
        )
        self.database_url = database_url
        self.exchange = None
        config = get_config()
        config.DATABASE_URL = self.database_url

    def _setup_cryptodotcom_xarizmi_db(self) -> None:
        config = get_config()
        config.DATABASE_URL = self.database_url
        run_db_migration()

    def _setup_exchange_table_records(self) -> None:
        with session_scope() as session:
            upsert_exchange(
                EXCHANGE,
                session=session,
            )

    def setup(self) -> None:
        self._setup_cryptodotcom_xarizmi_db()
        self._setup_exchange_table_records()

    def upsert_symbol(self, instrument_name: str) -> None:
        base, quote = instrument_name.split("_")
        with session_scope() as session:
            upsert_symbol(
                Symbol.build(
                    base_currency=base,
                    quote_currency=quote,
                    fee_currency="",
                    exchange=EXCHANGE_NAME,
                ),
                session=session,
            )

    def _insert_candlesticks_into_db(
        self, instrument_name: str, candlesticks: list[Candlestick]
    ) -> None:
        base, quote = instrument_name.split("_")
        with session_scope() as session:
            db_symbol = get_symbol(
                Symbol.build(
                    base_currency=base,
                    quote_currency=quote,
                    fee_currency="",
                    exchange=EXCHANGE_NAME,
                ),
                session=session,
            )
            for candlestick in candlesticks:
                upsert_candlestick(
                    candlestick, symbol_id=db_symbol.id, session=session
                )

    def download_all_candlesticks_all_intervals_over_1min(
        self, instrument_name: str, verbose: bool = True
    ) -> None:
        self.upsert_symbol(instrument_name=instrument_name)
        failed_to_download = []
        for interval in [
            CandlestickTimeInterval.MONTH_1,
            CandlestickTimeInterval.DAY_14,
            CandlestickTimeInterval.DAY_7,
            CandlestickTimeInterval.DAY_1,
            CandlestickTimeInterval.HOUR_12,
            CandlestickTimeInterval.HOUR_4,
            CandlestickTimeInterval.HOUR_2,
            CandlestickTimeInterval.HOUR_1,
            CandlestickTimeInterval.MIN_30,
            CandlestickTimeInterval.MIN_15,
            CandlestickTimeInterval.MIN_5,
        ]:
            candlesticks = []
            try:
                candlesticks += self.get_all_candlesticks(
                    instrument_name=instrument_name,
                    interval=interval,
                    verbose=verbose,
                )
            except Exception as e:
                failed_to_download.append((interval, str(e)))
                raise e
            self._insert_candlesticks_into_db(
                instrument_name=instrument_name, candlesticks=candlesticks
            )
        print(f"Failed to download: {failed_to_download}")

    def download_all_candlesticks_all_intervals_under_1min(
        self,
        instrument_name: str,
        start_year: int = 2015,
        verbose: bool = True,
    ) -> None:
        self.upsert_symbol(instrument_name=instrument_name)
        failed_to_downloads = []
        for year in range(datetime.datetime.today().year, start_year - 1, -1):

            for month in range(12, 0, -1):
                try:
                    candlesticks = self.get_all_candlesticks(
                        instrument_name=instrument_name,
                        min_datetime=datetime.datetime(year, month, 1)
                        - datetime.timedelta(days=1),
                        max_datetime=datetime.datetime(year, month, 1)
                        + datetime.timedelta(days=32),
                        interval=CandlestickTimeInterval.MIN_1,
                        verbose=verbose,
                    )
                except Exception as e:
                    failed_to_downloads.append((year, month, str(e)))
                    raise e
                self._insert_candlesticks_into_db(
                    instrument_name=instrument_name, candlesticks=candlesticks
                )
        print(f"Failed to download={failed_to_downloads}")

    def download_all_candlesticks_all_intervals(
        self,
        instrument_name: str,
        start_year: int = 2015,
        verbose: bool = True,
    ) -> None:
        self.download_all_candlesticks_all_intervals_over_1min(
            instrument_name=instrument_name, verbose=verbose
        )
        self.download_all_candlesticks_all_intervals_under_1min(
            instrument_name=instrument_name,
            start_year=start_year,
            verbose=verbose,
        )

    def download_all_candlesticks_all_intervals_in_past_few_minutes(
        self,
        instrument_name: str,
        minutes_before: int = 10,
        verbose: bool = True,
    ) -> None:
        self.upsert_symbol(instrument_name=instrument_name)
        min_datetime = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(
            minutes=minutes_before
        )
        for interval in CandlestickTimeInterval.__members__:
            candlesticks = self.get_all_candlesticks(
                instrument_name=instrument_name,
                min_datetime=min_datetime,
                max_datetime=None,
                interval=interval,
                verbose=verbose,
            )
            self._insert_candlesticks_into_db(
                instrument_name=instrument_name, candlesticks=candlesticks
            )

    def get_candlesticks_count(self) -> int:
        with session_scope() as session:
            return cast(int, session.query(DbCandlestick).count())

    def download_current_portfolio(self) -> None:
        with session_scope() as session:
            portfolio_items = self.get_user_balance_summary()
            for item in portfolio_items:
                upsert_symbol(symbol=item.symbol, session=session)
            bulk_upsert_portfolio_item(
                portfolio_items=portfolio_items, session=session
            )

    def get_portfolio_between_dates(
        self,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime,
    ) -> Portfolio:
        portfolio: Portfolio | None = None
        with session_scope() as session:
            portfolio = get_portfolio_items_between_dates(
                session=session,
                start_date=start_datetime,
                end_date=end_datetime,
            )
            for item in portfolio.items:
                item.datetime = item.datetime.replace(tzinfo=pytz.UTC)
        return portfolio

    def get_portfolio_on_date(
        self, start_datetime: datetime.datetime
    ) -> Portfolio:
        portfolio: Portfolio | None = None
        with session_scope() as session:
            portfolio = get_portfolio_items_between_dates(
                session=session,
                start_date=start_datetime,
                end_date=start_datetime + datetime.timedelta(days=1),
            )
            for item in portfolio.items:
                item.datetime = item.datetime.replace(tzinfo=pytz.UTC)
        return portfolio

    def get_portfolio_ratio_on_date(
        self, start_datetime: datetime.datetime
    ) -> Any:
        past_portfolio = self.get_portfolio_on_date(
            start_datetime=start_datetime
        )
        current_portfolio = self.get_current_portfolio()
        return current_portfolio / past_portfolio

    def create_buy_limit_order_xarizmi_insert_in_db(
        self,
        instrument_name: str,
        quantity: str | float,
        price: str | float,
    ) -> Order:
        order = self.create_buy_limit_order_xarizmi(
            instrument_name=instrument_name,
            quantity=quantity,
            price=price,
        )
        with session_scope() as session:
            upsert_order(
                order=order,
                session=session,
            )
        return order

    def get_order_details_in_xarizmi_update_in_db(
        self,
        order_id: str,
        session: Any = None,
    ) -> Order:
        order = self.get_order_details_in_xarizmi(
            order_id=order_id,
        )
        if session is None:
            with session_scope() as session:
                upsert_order(
                    order=order,
                    session=session,
                )
            return order
        else:
            upsert_order(
                order=order,
                session=session,
            )
            return order

    def _query_active_orders_in_db(
        self, instrument_name: str, session: Any = None
    ) -> list[Order]:
        symbol = get_xarizmi_symbol_from_instrument_name(instrument_name)
        orders = get_active_orders(
            session=session,
            symbol=symbol,
        )
        return orders

    def query_all_active_orders_get_details_update_in_db(
        self, instrument_name: str
    ) -> None:
        with session_scope() as session:
            orders = self._query_active_orders_in_db(
                instrument_name=instrument_name, session=session
            )
            for order in orders:
                if order.order_id is not None:
                    self.get_order_details_in_xarizmi_update_in_db(
                        order_id=order.order_id,
                    )

    def delete_cancelled_orders(self) -> None:
        with session_scope() as session:
            delete_all_cancelled_orders(session=session)


def get_historical_candlesticks_from_db(
    client: CryptoDbApiClient, instrument_name: str
) -> CandlestickChart:
    symbol = get_xarizmi_symbol_from_instrument_name(instrument_name)
    with session_scope() as session:
        candlestick_chart = get_filtered_candlesticks(
            session=session,
            symbol=symbol,
            filter_by_interval_type=IntervalTypeEnum.DAY_7,
            skip=0,
            limit=10000000,
        )
        return candlestick_chart
