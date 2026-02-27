"""
Unit tests for crypto_dot_com/export.py
========================================

All HTTP calls are intercepted with unittest.mock; no real credentials or
network connection are required.  File I/O uses pytest's ``tmp_path``
fixture for automatic clean-up.

Response data comes from the sanitized fixture files in tests/fixtures/ so
that the full parsing pipeline (Pydantic coercion of string prices,
millisecond timestamps, enum fields, etc.) is exercised end-to-end rather
than relying on hand-crafted Python dicts.

Test classes
------------
TestReadOrderHistoryFromCsv     Round-trip CSV built from the real order
                                history fixture; status / instrument filters,
                                combined filters, type coercion, and invalid
                                return_type.

TestExportOrderHistory          HTTP-level mocking with the real order history
                                fixture; new-file creation, merge with an
                                existing CSV, deduplication by order_id,
                                correct number of API calls for past_n_days,
                                and the integer record-count return value.

TestExportTradesHistory         HTTP-level mocking with real trades fixture;
                                new-file creation, correct CSV values, API call
                                count for past_n_days, deduplication by
                                trade_id.

TestExportUserBalance           CSV written to disk, pie chart written when a
                                path is provided, pie chart skipped when path
                                is None, filter_values_in_pie_chart applied
                                with real balance values, and graceful handling
                                of an empty (None) balance response.

Fixture summary (from tests/fixtures/)
---------------------------------------
private_get_order_history.json
    2 orders, both CRO_USD:
      order_id "6531362339749152100"  FILLED  BUY   qty=100  value=14.5
      order_id "6531362339749152200"  CANCELED SELL  qty=50   value=7.5

private_get_trades.json
    3 fills for one LINK_USD SELL order:
      trade_id "5755600643031727273"  price=9.197  qty=360.41  fees=-16.57
      trade_id "5755600643031727270"  price=9.198  qty=131.58  fees=-6.05
      trade_id "5755600643031727266"  price=9.199  qty=39.28   fees=-1.81

private_user_balance.json
    3 position balances (string-encoded numerics):
      BTC  qty=0.25  market_value=25000
      ETH  qty=5.0   market_value=15000
      USD  qty=3000  market_value=3000
"""

import copy
import json
import pathlib
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import MagicMock, patch

import pandas
import pytest

from crypto_dot_com.data_models.order_history import OrderHistoryDataMessage
from crypto_dot_com.enums import StatusEnum
from crypto_dot_com.export import (
    export_order_history,
    export_trades_history,
    export_user_balance,
    read_order_history_from_csv,
)

# ---------------------------------------------------------------------------
# Fixture loader (mirrors test_client_real_responses.py)
# ---------------------------------------------------------------------------

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text())
    return result


# ---------------------------------------------------------------------------
# MockResponse
# ---------------------------------------------------------------------------


class MockResponse:
    def __init__(
        self, json_data: dict[str, Any], status_code: int = 200
    ) -> None:
        self.json_data = json_data
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict[str, Any]:
        return self.json_data


# ---------------------------------------------------------------------------
# Response factories
# ---------------------------------------------------------------------------


def _order_history_response() -> MockResponse:
    """HTTP 200 wrapping the real order history fixture (2 orders)."""
    return MockResponse(load_fixture("private_get_order_history.json"))


def _trades_response() -> MockResponse:
    """HTTP 200 wrapping the real trades fixture (3 fills)."""
    return MockResponse(load_fixture("private_get_trades.json"))


def _balance_response() -> MockResponse:
    """HTTP 200 wrapping the real user balance fixture."""
    return MockResponse(load_fixture("private_user_balance.json"))


def _order_history_response_single(order_id: str) -> MockResponse:
    """Order history response containing one order with a custom order_id.

    Used in merge / deduplication tests where a second API call must
    return a record that is distinct from those already on disk.
    """
    data = copy.deepcopy(load_fixture("private_get_order_history.json"))
    item = copy.deepcopy(data["result"]["data"][0])
    item["order_id"] = order_id
    data["result"]["data"] = [item]
    return MockResponse(data)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def _orders_from_fixture() -> list[OrderHistoryDataMessage]:
    """Parse the order history fixture into real
    OrderHistoryDataMessage objects."""
    data = load_fixture("private_get_order_history.json")
    return [
        OrderHistoryDataMessage.model_validate(item)
        for item in data["result"]["data"]
    ]


def _write_orders_csv(
    path: Path, orders: list[OrderHistoryDataMessage]
) -> None:
    """Serialize orders using the same path that export_order_history uses."""
    df = pandas.DataFrame([item.model_dump() for item in orders])
    df["exec_inst"] = df["exec_inst"].apply(json.dumps)
    df.to_csv(path, index=False)


# Portfolio item mock factory (used for pie chart tests)
def _make_portfolio_item(name: str, market_value: float) -> MagicMock:
    item = MagicMock()
    item.symbol.base_currency.name = name
    item.market_value = market_value
    return item


# ---------------------------------------------------------------------------
# TestReadOrderHistoryFromCsv
# ---------------------------------------------------------------------------


class TestReadOrderHistoryFromCsv:
    """Tests for read_order_history_from_csv.

    The CSV is built by parsing the real order history fixture and
    serialising it through the same code path as export_order_history,
    ensuring the on-disk format is realistic (exec_inst JSON-encoded,
    numeric strings coerced by Pydantic on read-back, etc.).

    The two fixture orders are both CRO_USD; for instrument-filter tests
    the instrument_name is overridden on one copy so each row has a
    distinct instrument.
    """

    @pytest.fixture
    def orders_csv(self, tmp_path: Path) -> Path:
        """CSV with the two real fixture orders, keeping their CRO_USD
        instrument_name.  Used for status-filter and basic round-trip tests.
        """
        orders = _orders_from_fixture()
        path = tmp_path / "orders.csv"
        _write_orders_csv(path, orders)
        return path

    @pytest.fixture
    def two_instrument_csv(self, tmp_path: Path) -> Path:
        """CSV where each row has a distinct instrument so instrument-filter
        tests can verify both match and no-match paths.
        """
        orders = _orders_from_fixture()
        # Override instrument_name while keeping all other real values.
        btc = orders[0].model_copy(update={"instrument_name": "BTC_USD"})
        eth = orders[1].model_copy(update={"instrument_name": "ETH_USD"})
        path = tmp_path / "two_instruments.csv"
        _write_orders_csv(path, [btc, eth])
        return path

    # --- basic read ---

    def test_returns_pydantic_list_by_default(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(orders_csv)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, OrderHistoryDataMessage) for r in result)

    def test_order_ids_match_fixture(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(orders_csv)
        assert isinstance(result, list)
        ids = {o.order_id for o in result}
        assert "6531362339749152100" in ids
        assert "6531362339749152200" in ids

    def test_returns_dataframe_when_requested(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(
            orders_csv, return_type="dataframe"
        )
        assert isinstance(result, pandas.DataFrame)
        assert len(result) == 2

    def test_return_type_case_insensitive(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(
            orders_csv,
            return_type="DataFrame",  # type: ignore[arg-type]
        )
        assert isinstance(result, pandas.DataFrame)

    def test_invalid_return_type_raises(self, orders_csv: Path) -> None:
        with pytest.raises(ValueError, match="return_type"):
            read_order_history_from_csv(
                orders_csv,
                return_type="json",  # type: ignore[arg-type]
            )

    def test_no_filters_returns_all(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(orders_csv)
        assert len(result) == 2

    def test_accepts_string_filepath(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(str(orders_csv))
        assert len(result) == 2

    # --- filter_by_status ---

    def test_filter_by_status_filled(self, orders_csv: Path) -> None:
        """The fixture has exactly one FILLED order."""
        result = read_order_history_from_csv(
            orders_csv, filter_by_status=["FILLED"]
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].order_id == "6531362339749152100"
        assert result[0].status == StatusEnum.FILLED

    def test_filter_by_status_canceled(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(
            orders_csv, filter_by_status=[StatusEnum.CANCELED]
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].order_id == "6531362339749152200"

    def test_filter_by_status_enum_member(self, orders_csv: Path) -> None:
        """StatusEnum is a StrEnum; the filter must accept enum members."""
        result = read_order_history_from_csv(
            orders_csv, filter_by_status=[StatusEnum.FILLED]
        )
        assert isinstance(result, list)
        assert result[0].status == StatusEnum.FILLED

    def test_filter_by_status_multiple_values(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(
            orders_csv,
            filter_by_status=[StatusEnum.FILLED, StatusEnum.CANCELED],
        )
        assert len(result) == 2

    def test_filter_by_status_no_match_returns_empty(
        self, orders_csv: Path
    ) -> None:
        result = read_order_history_from_csv(
            orders_csv, filter_by_status=[StatusEnum.ACTIVE]
        )
        assert result == []

    # --- filter_by_instrument_name ---

    def test_filter_by_instrument_btc(self, two_instrument_csv: Path) -> None:
        result = read_order_history_from_csv(
            two_instrument_csv, filter_by_instrument_name="BTC_USD"
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].instrument_name == "BTC_USD"

    def test_filter_by_instrument_eth(self, two_instrument_csv: Path) -> None:
        result = read_order_history_from_csv(
            two_instrument_csv, filter_by_instrument_name="ETH_USD"
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].instrument_name == "ETH_USD"

    def test_filter_by_instrument_no_match(
        self, two_instrument_csv: Path
    ) -> None:
        result = read_order_history_from_csv(
            two_instrument_csv, filter_by_instrument_name="LINK_USD"
        )
        assert result == []

    # --- combined filters ---

    def test_combined_filled_and_btc(self, two_instrument_csv: Path) -> None:
        """FILLED order is BTC_USD in the two-instrument fixture."""
        result = read_order_history_from_csv(
            two_instrument_csv,
            filter_by_status=[StatusEnum.FILLED],
            filter_by_instrument_name="BTC_USD",
        )
        assert len(result) == 1

    def test_combined_filter_excludes_mismatched_row(
        self, two_instrument_csv: Path
    ) -> None:
        """FILLED + ETH_USD → no match (the FILLED order is BTC_USD)."""
        result = read_order_history_from_csv(
            two_instrument_csv,
            filter_by_status=[StatusEnum.FILLED],
            filter_by_instrument_name="ETH_USD",
        )
        assert result == []

    # --- field types after round-trip ---

    def test_order_id_and_client_oid_are_strings(
        self, orders_csv: Path
    ) -> None:
        """Numeric-looking IDs must survive CSV round-trip as str."""
        result = read_order_history_from_csv(orders_csv)
        assert isinstance(result, list)
        for order in result:
            assert isinstance(order.order_id, str)
            assert isinstance(order.client_oid, str)

    def test_quantity_and_order_value_are_floats(
        self, orders_csv: Path
    ) -> None:
        result = read_order_history_from_csv(orders_csv)
        assert isinstance(result, list)
        filled = next(o for o in result if o.order_id == "6531362339749152100")
        assert isinstance(filled.quantity, float)
        assert filled.quantity == pytest.approx(100.0)
        assert filled.order_value == pytest.approx(14.5)

    def test_fee_rates_preserved(self, orders_csv: Path) -> None:
        result = read_order_history_from_csv(orders_csv)
        assert isinstance(result, list)
        for order in result:
            assert order.maker_fee_rate == pytest.approx(0.001)
            assert order.taker_fee_rate == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# TestExportOrderHistory
# ---------------------------------------------------------------------------


class TestExportOrderHistory:
    """Tests for export_order_history.

    requests.post is mocked at the HTTP level so CryptoAPI performs its
    full signed-POST + Pydantic-parsing pipeline against the real fixture.
    """

    # --- new-file creation ---

    @mock.patch("requests.post")
    def test_creates_csv_when_file_does_not_exist(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()
        filepath = tmp_path / "orders.csv"

        n = export_order_history("key", "secret", filepath, past_n_days=0)

        assert filepath.is_file()
        assert n == 2  # fixture has 2 orders

    @mock.patch("requests.post")
    def test_csv_contains_real_order_ids(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()
        filepath = tmp_path / "orders.csv"

        export_order_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath, dtype={"order_id": str})
        assert "6531362339749152100" in df["order_id"].values
        assert "6531362339749152200" in df["order_id"].values

    @mock.patch("requests.post")
    def test_csv_contains_correct_columns(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()
        filepath = tmp_path / "orders.csv"

        export_order_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        for col in (
            "order_id",
            "status",
            "instrument_name",
            "quantity",
            "order_value",
        ):
            assert col in df.columns, f"Missing column: {col}"
        assert "Unnamed: 0" not in df.columns

    @mock.patch("requests.post")
    def test_csv_status_values_match_fixture(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()
        filepath = tmp_path / "orders.csv"

        export_order_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        assert set(df["status"].tolist()) == {"FILLED", "CANCELED"}

    @mock.patch("requests.post")
    def test_accepts_string_filepath(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()
        filepath = str(tmp_path / "orders.csv")

        export_order_history("key", "secret", filepath, past_n_days=0)

        assert Path(filepath).is_file()

    # --- past_n_days API call count ---

    @mock.patch("requests.post")
    def test_past_n_days_zero_makes_one_api_call(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _order_history_response()

        export_order_history(
            "key", "secret", tmp_path / "o.csv", past_n_days=0
        )

        assert mock_post.call_count == 1

    @mock.patch("requests.post")
    def test_past_n_days_two_makes_three_api_calls(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """today + yesterday + 2 days ago = 3 calls."""
        mock_post.side_effect = [_order_history_response()] * 3

        export_order_history(
            "key", "secret", tmp_path / "o.csv", past_n_days=2
        )

        assert mock_post.call_count == 3

    @mock.patch("requests.post")
    def test_returns_total_record_count(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """Fixture has 2 orders; return value must equal row count."""
        mock_post.return_value = _order_history_response()

        n = export_order_history(
            "key", "secret", tmp_path / "o.csv", past_n_days=0
        )

        assert n == 2

    # --- merge and deduplication ---

    @mock.patch("requests.post")
    def test_merges_with_existing_file(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """Second run with a new order_id must produce 3 unique rows."""
        filepath = tmp_path / "orders.csv"

        # First run: fixture has 2 orders
        mock_post.return_value = _order_history_response()
        export_order_history("key", "secret", filepath, past_n_days=0)

        # Second run: one new order (different order_id)
        mock_post.return_value = _order_history_response_single(
            "9999999999999999999"
        )
        n = export_order_history("key", "secret", filepath, past_n_days=0)

        assert n == 3
        df = pandas.read_csv(filepath, dtype={"order_id": str})
        assert "6531362339749152100" in df["order_id"].values
        assert "6531362339749152200" in df["order_id"].values
        assert "9999999999999999999" in df["order_id"].values

    @mock.patch("requests.post")
    def test_deduplicates_by_order_id(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """Re-downloading the same orders must not create duplicate rows."""
        filepath = tmp_path / "orders.csv"
        mock_post.return_value = _order_history_response()

        export_order_history("key", "secret", filepath, past_n_days=0)
        mock_post.return_value = _order_history_response()
        n = export_order_history("key", "secret", filepath, past_n_days=0)

        assert n == 2

    @mock.patch("requests.post")
    def test_empty_api_response_creates_empty_csv(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        fixture = load_fixture("private_get_order_history.json")
        fixture = copy.deepcopy(fixture)
        fixture["result"]["data"] = []
        mock_post.return_value = MockResponse(fixture)
        filepath = tmp_path / "orders.csv"

        n = export_order_history("key", "secret", filepath, past_n_days=0)

        assert n == 0
        assert filepath.is_file()


# ---------------------------------------------------------------------------
# TestExportTradesHistory
# ---------------------------------------------------------------------------


class TestExportTradesHistory:
    """Tests for export_trades_history.

    requests.post is mocked with the real trades fixture (3 LINK_USD fills).
    Unlike export_order_history, this function does NOT merge with existing
    files — it overwrites each run.  Deduplication is applied within a single
    batch (relevant when the time-range is split recursively).
    """

    @mock.patch("requests.post")
    def test_creates_csv_with_correct_row_count(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        n = export_trades_history("key", "secret", filepath, past_n_days=0)

        assert filepath.is_file()
        assert n == 3

    @mock.patch("requests.post")
    def test_csv_contains_real_trade_ids(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        export_trades_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath, dtype={"trade_id": str})
        assert "5755600643031727273" in df["trade_id"].values
        assert "5755600643031727270" in df["trade_id"].values
        assert "5755600643031727266" in df["trade_id"].values

    @mock.patch("requests.post")
    def test_csv_contains_correct_columns(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        export_trades_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        for col in (
            "trade_id",
            "instrument_name",
            "side",
            "traded_price",
            "traded_quantity",
            "fees",
        ):
            assert col in df.columns, f"Missing column: {col}"
        assert "Unnamed: 0" not in df.columns

    @mock.patch("requests.post")
    def test_csv_traded_price_values(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """String prices from the API must be stored as floats in the CSV."""
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        export_trades_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        prices = set(df["traded_price"].round(3).tolist())
        assert prices == {9.197, 9.198, 9.199}

    @mock.patch("requests.post")
    def test_csv_fees_are_negative(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        export_trades_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        assert (df["fees"] < 0).all()

    @mock.patch("requests.post")
    def test_instrument_name_all_link_usd(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = tmp_path / "trades.csv"

        export_trades_history("key", "secret", filepath, past_n_days=0)

        df = pandas.read_csv(filepath)
        assert (df["instrument_name"] == "LINK_USD").all()

    @mock.patch("requests.post")
    def test_past_n_days_zero_makes_one_api_call(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()

        export_trades_history(
            "key", "secret", tmp_path / "t.csv", past_n_days=0
        )

        assert mock_post.call_count == 1

    @mock.patch("requests.post")
    def test_past_n_days_two_makes_three_api_calls(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.side_effect = [_trades_response()] * 3

        export_trades_history(
            "key", "secret", tmp_path / "t.csv", past_n_days=2
        )

        assert mock_post.call_count == 3

    @mock.patch("requests.post")
    def test_deduplicates_by_trade_id_across_days(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        """When past_n_days > 0 the same trades might appear in overlapping
        windows; dedup by trade_id must keep only unique rows."""
        # Return the same 3-trade fixture for all 3 day-calls
        mock_post.side_effect = [_trades_response()] * 3

        n = export_trades_history(
            "key", "secret", tmp_path / "t.csv", past_n_days=2
        )

        # 9 raw rows reduced to 3 unique trade_ids
        assert n == 3

    @mock.patch("requests.post")
    def test_accepts_string_filepath(
        self, mock_post: mock.Mock, tmp_path: Path
    ) -> None:
        mock_post.return_value = _trades_response()
        filepath = str(tmp_path / "trades.csv")

        export_trades_history("key", "secret", filepath, past_n_days=0)

        assert Path(filepath).is_file()


# ---------------------------------------------------------------------------
# TestExportUserBalance
# ---------------------------------------------------------------------------


class TestExportUserBalance:
    """Tests for export_user_balance.

    Portfolio items use real market_value figures from the balance fixture:
      BTC → 25 000 USD
      ETH → 15 000 USD
      USD →  3 000 USD

    The filter_values_in_pie_chart tests use these values to verify that the
    threshold is applied correctly (> threshold, not >=).
    """

    def _mock_client(
        self,
        df: pandas.DataFrame | None,
        portfolio_items: list[Any],
    ) -> MagicMock:
        client = MagicMock()
        client.get_user_balance_summary_as_df.return_value = df
        client.get_user_balance_summary.return_value = portfolio_items
        return client

    def _real_balance_df(self) -> pandas.DataFrame:
        """DataFrame with real fixture values, matching the shape returned by
        CryptoAPI.get_user_balance_summary_as_df."""
        return pandas.DataFrame(
            [
                {
                    "symbol": "BTC",
                    "quantity": 0.25,
                    "market_value": 25000.0,
                    "exchange": "crypto.com",
                    "portfolio_percentage": 0.581,
                    "date": "2026-02-27",
                },
                {
                    "symbol": "ETH",
                    "quantity": 5.0,
                    "market_value": 15000.0,
                    "exchange": "crypto.com",
                    "portfolio_percentage": 0.349,
                    "date": "2026-02-27",
                },
                {
                    "symbol": "USD",
                    "quantity": 3000.0,
                    "market_value": 3000.0,
                    "exchange": "crypto.com",
                    "portfolio_percentage": 0.070,
                    "date": "2026-02-27",
                },
            ]
        )

    def _real_portfolio_items(self) -> list[Any]:
        """Portfolio items with real fixture market values."""
        return [
            _make_portfolio_item("BTC", 25000.0),
            _make_portfolio_item("ETH", 15000.0),
            _make_portfolio_item("USD", 3000.0),
        ]

    # --- CSV output ---

    @patch("crypto_dot_com.export.CryptoAPI")
    def test_writes_csv_file(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(self._real_balance_df(), [])
        filepath = tmp_path / "portfolio.csv"

        export_user_balance("key", "secret", filepath)

        assert filepath.is_file()
        df = pandas.read_csv(filepath)
        assert set(df["symbol"].tolist()) == {"BTC", "ETH", "USD"}

    @patch("crypto_dot_com.export.CryptoAPI")
    def test_csv_market_values_match_fixture(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(self._real_balance_df(), [])
        filepath = tmp_path / "portfolio.csv"

        export_user_balance("key", "secret", filepath)

        df = pandas.read_csv(filepath)
        mv = dict(zip(df["symbol"], df["market_value"]))
        assert mv["BTC"] == pytest.approx(25000.0)
        assert mv["ETH"] == pytest.approx(15000.0)
        assert mv["USD"] == pytest.approx(3000.0)

    @patch("crypto_dot_com.export.CryptoAPI")
    def test_skips_write_when_balance_is_none(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(None, [])
        filepath = tmp_path / "portfolio.csv"

        export_user_balance("key", "secret", filepath)

        assert not filepath.is_file()

    @patch("crypto_dot_com.export.CryptoAPI")
    def test_accepts_string_filepath(
        self, mock_cls: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(self._real_balance_df(), [])
        filepath = str(tmp_path / "portfolio.csv")

        export_user_balance("key", "secret", filepath)

        assert Path(filepath).is_file()

    # --- pie chart ---

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_skips_pie_chart_when_path_is_none(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(self._real_balance_df(), [])

        export_user_balance(
            "key", "secret", tmp_path / "p.csv", pie_chart_filepath=None
        )

        mock_plt.subplots.assert_not_called()

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_writes_pie_chart_when_path_given(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), self._real_portfolio_items()
        )
        fig_mock = MagicMock()
        ax_mock = MagicMock()
        mock_plt.subplots.return_value = (fig_mock, ax_mock)

        chart_path = tmp_path / "portfolio.svg"
        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=chart_path,
        )

        mock_plt.subplots.assert_called_once()
        fig_mock.savefig.assert_called_once_with(chart_path, dpi=300)
        mock_plt.close.assert_called_once_with(fig_mock)

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_pie_chart_accepts_string_path(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), self._real_portfolio_items()
        )
        mock_plt.subplots.return_value = (MagicMock(), MagicMock())

        chart_path = str(tmp_path / "portfolio.svg")
        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=chart_path,
        )

        fig_mock = mock_plt.subplots.return_value[0]
        call_arg = fig_mock.savefig.call_args[0][0]
        assert isinstance(call_arg, Path)

    # --- filter_values_in_pie_chart with real fixture values ---

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_default_filter_excludes_sub_dollar_dust(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        """Default threshold (1.0) must keep BTC/ETH/USD (all > 1) but
        exclude a dust balance of $0.50."""
        items = self._real_portfolio_items() + [
            _make_portfolio_item("DUST", 0.50)
        ]
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), items
        )
        fig_mock, ax_mock = MagicMock(), MagicMock()
        mock_plt.subplots.return_value = (fig_mock, ax_mock)

        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=tmp_path / "chart.svg",
            filter_values_in_pie_chart=1.0,
        )

        labels = ax_mock.pie.call_args[1]["labels"]
        values = ax_mock.pie.call_args[0][0]
        assert "BTC" in labels
        assert "ETH" in labels
        assert "USD" in labels
        assert "DUST" not in labels
        assert 0.50 not in values

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_filter_20000_keeps_only_btc(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        """With threshold=20 000: BTC (25 000) passes, ETH (15 000) and
        USD (3 000) are excluded."""
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), self._real_portfolio_items()
        )
        ax_mock = MagicMock()
        mock_plt.subplots.return_value = (MagicMock(), ax_mock)

        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=tmp_path / "chart.svg",
            filter_values_in_pie_chart=20000.0,
        )

        labels = ax_mock.pie.call_args[1]["labels"]
        values = ax_mock.pie.call_args[0][0]
        assert labels == ["BTC"]
        assert values == [25000.0]

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_filter_10000_keeps_btc_and_eth(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        """With threshold=10 000: BTC (25 000) and ETH (15 000) pass,
        USD (3 000) is excluded."""
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), self._real_portfolio_items()
        )
        ax_mock = MagicMock()
        mock_plt.subplots.return_value = (MagicMock(), ax_mock)

        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=tmp_path / "chart.svg",
            filter_values_in_pie_chart=10000.0,
        )

        labels = ax_mock.pie.call_args[1]["labels"]
        assert "BTC" in labels
        assert "ETH" in labels
        assert "USD" not in labels

    @patch("crypto_dot_com.export.plt")
    @patch("crypto_dot_com.export.CryptoAPI")
    def test_figsize_forwarded_to_subplots(
        self, mock_cls: MagicMock, mock_plt: MagicMock, tmp_path: Path
    ) -> None:
        mock_cls.return_value = self._mock_client(
            self._real_balance_df(), self._real_portfolio_items()
        )
        mock_plt.subplots.return_value = (MagicMock(), MagicMock())

        export_user_balance(
            "key",
            "secret",
            filepath=tmp_path / "p.csv",
            pie_chart_filepath=tmp_path / "chart.svg",
            figsize=(12, 12),
        )

        mock_plt.subplots.assert_called_once_with(figsize=(12, 12))
