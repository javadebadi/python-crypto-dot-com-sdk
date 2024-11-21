import datetime
from typing import Any

import pandas as pd
import pytz
import requests
from xarizmi.candlestick import Candlestick
from xarizmi.enums import IntervalTypeEnum
from xarizmi.utils.datetools import get_current_time_miliseconds
from xarizmi.utils.datetools import get_day_timestamps_nanoseconds

from crypto_dot_com.data_models import CreateOrderDataMessage
from crypto_dot_com.data_models import OrderHistoryDataMessage
from crypto_dot_com.data_models.crypto_dot_com import CryptoDotComErrorResponse
from crypto_dot_com.data_models.crypto_dot_com import CryptoDotComResponseType
from crypto_dot_com.data_models.request_message import CreateLimitOrderMessage
from crypto_dot_com.data_models.response import GetCandlestickDataMessage
from crypto_dot_com.data_models.response import GetUserBalanceDataMessage
from crypto_dot_com.data_models.summary import UserBalanceSummary
from crypto_dot_com.enums import TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM
from crypto_dot_com.enums import CandlestickTimeInterval
from crypto_dot_com.enums import CryptoDotComMethodsEnum
from crypto_dot_com.exceptions import BadPriceException
from crypto_dot_com.exceptions import BadQuantityException
from crypto_dot_com.request_builder import CryptoDotComRequestBuilder
from crypto_dot_com.request_builder import CryptoDotComUrlBuilder
from crypto_dot_com.settings import API_VERSION
from crypto_dot_com.settings import EXCHANGE_NAME
from crypto_dot_com.settings import ROOT_API_ENDPOINT
from crypto_dot_com.settings import log_json_response


class CryptoAPI:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        timeout: int = 1000,
        log_json_response_to_file: bool = False,
        logs_directory: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._base_url = ROOT_API_ENDPOINT + "/" + API_VERSION
        self.api_key = api_key
        self.api_secret = api_secret
        self.log_json_response_to_file = log_json_response_to_file
        self.logs_directory = logs_directory

    def _get_headers(self, method: str) -> dict[str, str]:
        if method in ["POST", "DELETE"]:
            return {"Content-Type": "application/json"}
        else:
            return {}

    def _get_public(
        self,
        method: CryptoDotComMethodsEnum,
        params: dict[str, Any],
    ) -> CryptoDotComResponseType:
        try:
            response = requests.get(
                CryptoDotComUrlBuilder(method=method).build(), params=params
            )
            if self.log_json_response_to_file is True:
                log_json_response(
                    response=response, logs_directory=self.logs_directory
                )
            if response.ok:
                response_data: CryptoDotComResponseType = (
                    CryptoDotComResponseType.model_validate(response.json())
                )
                return response_data
            else:
                print("Error code = ", response.status_code)
                print("Error message = ", response.json())
                raise NotImplementedError(f"{response.json()}")
        except Exception as e:
            print(
                f"Error code = {e}",
            )
            raise e

    def _post(
        self,
        method: CryptoDotComMethodsEnum,
        params: dict[str, Any],
        sign: bool = False,
        request_id: int | None = None,
    ) -> CryptoDotComResponseType:
        builder = CryptoDotComRequestBuilder(
            method=method,
            api_key=self.api_key,
            secret_key=self.api_secret,
            params=params,
            sign=sign,
            request_id=request_id,
        )
        request_data = builder.build()
        try:
            response = requests.post(
                request_data["url"],
                headers=request_data["headers"],
                data=request_data["data"],
            )
            if self.log_json_response_to_file is True:
                log_json_response(
                    response=response, logs_directory=self.logs_directory
                )
            if response.ok:
                response_data: CryptoDotComResponseType = (
                    CryptoDotComResponseType.model_validate(response.json())
                )

                return response_data
            else:
                print("Error code = ", response.status_code)
                print("Error message = ", response.json())
                error_response = CryptoDotComErrorResponse.model_validate(
                    response.json()
                )
                if error_response.code == 315:
                    raise BadPriceException(
                        f"code: {error_response.code} -"
                        f"msg: {error_response.message} -"
                        f"data: {builder} "
                    )
                if error_response.code == 308:
                    raise BadPriceException(
                        f"code: {error_response.code} -"
                        f"msg: {error_response.message} -"
                        f"data: {builder} "
                    )
                elif error_response.code == 213:
                    raise BadQuantityException(
                        f"code: {error_response.code} -"
                        f"msg: {error_response.message} -"
                        f"data: {builder} "
                    )
                else:
                    raise RuntimeError(str(error_response))

        except Exception as e:
            print(
                f"Error code = {e}",
            )
            raise e

    def get_order_history(
        self,
        start_time: int,
        end_time: int,
        limit: int = 100,  # MAX and Default value in API
        instrument_name: str | None = None,
    ) -> list[OrderHistoryDataMessage]:
        """ """
        response = self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_GET_ORDER_HISTORY,
            params={
                "instrument_name": instrument_name,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
            sign=True,
        )
        data = response.result["data"]  # type: ignore
        if len(data) < limit:
            return [
                OrderHistoryDataMessage.model_validate(item) for item in data
            ]
        else:
            # logic in case number of records exceeds API limit
            return self.get_order_history(
                instrument_name=instrument_name,
                start_time=start_time,
                end_time=((start_time + end_time) // 2 + 1),
                limit=limit,
            ) + self.get_order_history(
                instrument_name=instrument_name,
                start_time=((start_time + end_time) // 2),
                end_time=end_time,
                limit=limit,
            )

    def get_all_order_history_of_a_day(
        self,
        day: datetime.date,
        instrument_name: str | None = None,
    ) -> list[OrderHistoryDataMessage]:
        start_time, end_time = get_day_timestamps_nanoseconds(
            days_before=0, reference_date=day
        )
        return self.get_order_history(
            start_time=start_time,
            end_time=end_time,
            instrument_name=instrument_name,
        )

    def create_limit_order(
        self,
        instrument_name: str,
        quantity: str | float,
        side: str,
        price: str | float,
    ) -> CreateOrderDataMessage:
        params = CreateLimitOrderMessage.model_validate(
            {
                "instrument_name": instrument_name,
                "quantity": str(quantity),
                "side": str(side),
                "price": str(price),
            }
        )
        response = self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_CREATE_ORDER,
            params=params.model_dump(),
            sign=True,
        )
        return CreateOrderDataMessage.model_validate(response.result)

    def cancel_all_orders(self, instrument_name: str | None = None) -> None:
        """Method is asynchronous and only sends the confirmation"""
        self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_CANCEL_ALL_ORDERS,
            params={
                "instrument_name": instrument_name,
            },
            sign=True,
        )

    def cancel_order(self, order_id: str) -> None:
        self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_CANCEL_ORDER,
            params={
                "order_id": order_id,
            },
            sign=True,
        )

    def get_order_details(self, order_id: str) -> OrderHistoryDataMessage:
        response = self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_GET_ORDER_DETAILS,
            params={
                "order_id": order_id,
            },
            sign=True,
        )
        return OrderHistoryDataMessage.model_validate(response.result)

    def get_candlesticks(
        self,
        instrument_name: str,
        count: int = 25,
        timeframe: str = "1m",
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> list[Candlestick]:
        params = {
            "instrument_name": instrument_name,
            "count": count,
            "timeframe": CandlestickTimeInterval(timeframe).value,
        }
        if start_ts is not None:
            params["start_ts"] = start_ts
        if end_ts is not None:
            params["end_ts"] = end_ts
        response = self._get_public(
            method=CryptoDotComMethodsEnum.PUBLIC_GET_CANDLESTICK,
            params=params,
        )
        response_message = GetCandlestickDataMessage.model_validate(
            response.result
        )
        result = [
            Candlestick.model_validate(
                {
                    "open": item.o,
                    "close": item.c,
                    "high": item.h,
                    "low": item.l,
                    "volume": item.v,
                    "interval": item.t,  # ms
                    "symbol": {
                        "base_currency": {"name": ""},
                        "quote_currency": {
                            "name": response_message.instrument_name,
                        },
                        "fee_currency": {
                            "name": "",
                        },
                    },
                    "exchange": {
                        "name": EXCHANGE_NAME,
                    },
                    "interval_type": TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[  # noqa: E501
                        response_message.interval
                    ],
                    "datetime": datetime.datetime.fromtimestamp(
                        item.t / 1000, tz=pytz.UTC
                    ),
                }
            )
            for item in response_message.data
        ]
        return result

    def get_all_candlesticks(
        self,
        instrument_name: str,
        interval: CandlestickTimeInterval | str,
        n_steps: int = 300,
        verbose: bool = True,
    ) -> list[Candlestick]:

        if type(interval) is str:
            try:
                interval = CandlestickTimeInterval[interval]
            except KeyError:
                try:
                    interval = CandlestickTimeInterval(value=interval)
                except ValueError:
                    raise ValueError(
                        f"the given interval '{interval}' is not valid!"
                    )

        xarizmi_interval = TIME_INTERVAL_CRYPTO_DOT_COM_TO_XARIZMI_ENUM[
            interval  # type: ignore
        ]
        interval_miliseconds = IntervalTypeEnum.get_interval_in_miliseconds(
            xarizmi_interval
        )

        step = interval_miliseconds * n_steps  # type: ignore
        current_time = get_current_time_miliseconds()
        kline_data: list[Candlestick] = []
        i = 0
        while True:
            end_ts = current_time - i * step
            start_ts = end_ts - step
            new_kline_data = self.get_candlesticks(
                instrument_name=instrument_name,
                count=n_steps,
                timeframe=interval.value,  # type: ignore
                start_ts=start_ts,
                end_ts=end_ts,
            )
            if not new_kline_data:
                break
            else:
                i += 1
            kline_data += new_kline_data
            if verbose is True:
                print(
                    f"{datetime.datetime.fromtimestamp(start_ts // 1000)} -> "
                    f"{datetime.datetime.fromtimestamp(end_ts // 1000)}"
                )
                print(
                    f"Number of current records in memory: {len(kline_data)}"
                )
                print("................................")

        return kline_data

    def get_user_balance(self) -> list[GetUserBalanceDataMessage]:
        response = self._post(
            method=CryptoDotComMethodsEnum.PRIVATE_USER_BALANCE,
            params={},
            sign=True,
        )
        return [
            GetUserBalanceDataMessage.model_validate(item)
            for item in response.result["data"]  # type: ignore
        ]

    def get_user_balance_summary(self) -> list[UserBalanceSummary]:
        user_balances = self.get_user_balance()[0]
        if not user_balances:
            return []
        return [
            UserBalanceSummary(
                currency=item.instrument_name,
                market_value=item.market_value,
                quantity=item.quantity,
            )
            for item in user_balances.position_balances
        ]

    def get_user_balance_summary_as_df(
        self,
        include_portfolio_percentage: bool = True,
        include_date: bool = True,
    ) -> None | pd.DataFrame:
        data = self.get_user_balance_summary()
        if not data:
            return None
        df = pd.DataFrame(item.model_dump() for item in data)
        df.sort_values(by="market_value", ascending=False, inplace=True)
        if include_portfolio_percentage is True:
            df["portfolio_percentage"] = (
                df["market_value"] / sum(df["market_value"])
            ).apply(lambda x: round(x, 3))
        if include_date is True:
            df["date"] = datetime.date.today()
        return df
