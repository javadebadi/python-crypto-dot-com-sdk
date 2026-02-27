"""Export utilities for saving and loading crypto.com data locally.

When to use
-----------
Use the functions in this module when you want to **persist data beyond the
lifetime of a single session** or beyond crypto.com's 6-month API history
window.

``export_order_history``
    Downloads order history for a date range, saves it to a CSV file, and
    **merges** with any previously-saved data.  Duplicates (by ``order_id``)
    are removed automatically, so it is safe to run daily as an incremental
    update.

    Use this to build a long-term audit trail of your trades.  Crypto.com
    limits history retrieval to ~6 months; running this regularly lets you
    accumulate years of data locally.

``read_order_history_from_csv``
    Reads a CSV written by ``export_order_history``.  Returns either a list
    of typed ``OrderHistoryDataMessage`` Pydantic objects or a pandas
    ``DataFrame``.  Supports filtering by order status and instrument name.

    Use this for offline analysis, backtesting data prep, or feeding fills
    into a reporting pipeline.  The pydantic return type integrates cleanly
    with the xarizmi data model.

``export_user_balance``
    Fetches your current account holdings and saves a timestamped CSV
    snapshot.  Optionally generates a pie chart of portfolio allocation by
    market value.

    Use this for daily portfolio snapshots.  Comparing CSV snapshots over
    time reveals portfolio drift; the pie chart gives a quick visual summary.

Typical daily workflow (cron / task scheduler)::

    from crypto_dot_com.export import export_order_history, export_user_balance

    export_order_history(api_key, secret, "orders.csv", past_n_days=0)
    export_user_balance(
        api_key, secret,
        filepath="portfolio.csv",
        pie_chart_filepath="portfolio.svg",
    )

Then load for offline analysis::

    from crypto_dot_com.export import read_order_history_from_csv
    from crypto_dot_com.enums import StatusEnum

    filled = read_order_history_from_csv(
        "orders.csv",
        filter_by_status=[StatusEnum.FILLED],
        filter_by_instrument_name="BTC_USD",
    )
"""

import datetime
import json
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import pandas

from crypto_dot_com.client import CryptoAPI
from crypto_dot_com.data_models.order_history import OrderHistoryDataMessage
from crypto_dot_com.data_models.response import TradeHistoryDataMessage
from crypto_dot_com.enums import StatusEnum


def read_order_history_from_csv(
    filepath: str | Path,
    filter_by_status: list[StatusEnum] | list[str] | None = None,
    filter_by_instrument_name: str | None = None,
    return_type: Literal["pydantic", "dataframe"] = "pydantic",
) -> list[OrderHistoryDataMessage] | pandas.DataFrame:
    """Read order history previously saved by :func:`export_order_history`.

    Parameters
    ----------
    filepath:
        Path to the CSV file written by ``export_order_history``.
    filter_by_status:
        Keep only orders whose ``status`` matches one of the given values.
        Accepts both plain strings (``"FILLED"``) and
        :class:`~crypto_dot_com.enums.StatusEnum` members interchangeably.
        Pass ``None`` (default) to return all statuses.
    filter_by_instrument_name:
        Keep only orders for this instrument (e.g. ``"BTC_USD"``).
        Pass ``None`` (default) to return all instruments.
    return_type:
        ``"pydantic"`` (default) — returns a list of
        :class:`~crypto_dot_com.data_models.order_history.OrderHistoryDataMessage`
        objects ready for use with the xarizmi framework.

        ``"dataframe"`` — returns a :class:`pandas.DataFrame` suitable for
        quick inspection, CSV re-export, or further pandas processing.

    Returns
    -------
    list[OrderHistoryDataMessage] | pandas.DataFrame
        Filtered order records in the requested format.

    Raises
    ------
    ValueError
        If ``return_type`` is not ``"pydantic"`` or ``"dataframe"``.

    When to use
    -----------
    Call this after ``export_order_history`` has built a local CSV.  Use the
    pydantic return type when you need typed objects (e.g. to compute P&L or
    feed into a strategy).  Use the dataframe when you want to slice, pivot,
    or re-export the data quickly.

    Examples
    --------
    >>> filled = read_order_history_from_csv(
    ...     "orders.csv",
    ...     filter_by_status=[StatusEnum.FILLED],
    ...     filter_by_instrument_name="BTC_USD",
    ... )
    >>> df = read_order_history_from_csv("orders.csv", return_type="dataframe")
    """
    df = pandas.read_csv(filepath)
    df = df.astype({"client_oid": "str", "order_id": "str"})

    if filter_by_status is not None:
        # Normalise to plain strings — works for both str and StrEnum members
        # (StatusEnum is a StrEnum, so str(member) == member.value)
        status_strings = [str(item) for item in filter_by_status]
        df = df[df["status"].isin(status_strings)]

    if filter_by_instrument_name is not None:
        df = df[df["instrument_name"] == filter_by_instrument_name]

    if return_type.lower() == "pydantic":
        records = df.to_dict(orient="records")
        # pandas reads missing optional fields as float NaN; normalise to None
        # so that pydantic accepts them for str | None fields.
        clean_records: list[dict[str, Any]] = [
            {
                str(k): (
                    None if isinstance(v, float) and pandas.isna(v) else v
                )
                for k, v in row.items()
            }
            for row in records
        ]
        data: list[OrderHistoryDataMessage] = [
            OrderHistoryDataMessage(**row) for row in clean_records
        ]
        return data
    elif return_type.lower() == "dataframe":
        return df
    else:
        raise ValueError(
            "return_type should be one of ['dataframe', 'pydantic']"
        )


def export_order_history(
    api_key: str,
    secret_key: str,
    filepath: str | Path,
    past_n_days: int = 0,
) -> int:
    """Download and save order history to a CSV file.

    Fetches order history from the crypto.com API for today and, optionally,
    the preceding ``past_n_days`` calendar days.  If a file already exists at
    ``filepath``, existing records are merged with the new data and duplicates
    (by ``order_id``) are removed — so the function is safe to run repeatedly
    as an incremental daily update.

    Parameters
    ----------
    api_key:
        Your crypto.com API key.
    secret_key:
        Your crypto.com API secret.
    filepath:
        Destination path for the CSV file.  Created on first run;
        merged and deduplicated on subsequent runs.
    past_n_days:
        How many additional days before today to include.  ``0`` (default)
        downloads today's orders only.  ``7`` downloads today plus the
        previous 7 days (8 days total).

    Returns
    -------
    int
        Total number of unique records in the file after the update.

    Notes
    -----
    Crypto.com limits order history retrieval to roughly **6 months** in the
    past.  Run this function regularly (e.g. daily via cron) to maintain a
    longer local record.

    When to use
    -----------
    Use to build a persistent, deduplicated audit trail of all your trades::

        # Daily incremental update (today only)
        n = export_order_history(
            api_key, secret, "orders.csv", past_n_days=0)

        # Back-fill on first run
        n = export_order_history(
            api_key, secret, "orders.csv", past_n_days=180)
        print(f"Saved {n} records")
    """
    filepath = Path(filepath) if isinstance(filepath, str) else filepath

    client = CryptoAPI(
        api_key=api_key,
        api_secret=secret_key,
        log_json_response_to_file=False,
    )

    # Download: today (i=0) then the past `past_n_days` calendar days (i=1…n)
    reference_date = datetime.date.today()
    all_data: list[OrderHistoryDataMessage] = []
    for i in range(0, past_n_days + 1):
        print("Getting orders of past {i} days")
        day = reference_date - datetime.timedelta(days=i)
        data = client.get_all_order_history_of_a_day(
            instrument_name=None, day=day
        )
        all_data.extend(data)

    # Merge with existing file to preserve records outside the download window
    if filepath.is_file():
        prev_data = read_order_history_from_csv(
            filepath=filepath, return_type="pydantic"
        )
        all_data.extend(prev_data)  # type: ignore

    df = pandas.DataFrame([item.model_dump() for item in all_data])
    if not df.empty:
        df["exec_inst"] = df["exec_inst"].apply(json.dumps)
    df.drop_duplicates(subset="order_id", keep="first", inplace=True)
    df.to_csv(filepath, index=False)
    return len(df)


def export_trades_history(
    api_key: str,
    secret_key: str,
    filepath: str | Path,
    past_n_days: int = 0,
) -> int:
    """Download and save order history to a CSV file.

    Fetches order history from the crypto.com API for today and, optionally,
    the preceding ``past_n_days`` calendar days.  If a file already exists at
    ``filepath``, existing records are merged with the new data and duplicates
    (by ``order_id``) are removed — so the function is safe to run repeatedly
    as an incremental daily update.

    Parameters
    ----------
    api_key:
        Your crypto.com API key.
    secret_key:
        Your crypto.com API secret.
    filepath:
        Destination path for the CSV file.  Created on first run;
        merged and deduplicated on subsequent runs.
    past_n_days:
        How many additional days before today to include.  ``0`` (default)
        downloads today's orders only.  ``7`` downloads today plus the
        previous 7 days (8 days total).

    Returns
    -------
    int
        Total number of unique records in the file after the update.

    Notes
    -----
    Crypto.com limits order history retrieval to roughly **6 months** in the
    past.  Run this function regularly (e.g. daily via cron) to maintain a
    longer local record.

    When to use
    -----------
    Use to build a persistent, deduplicated audit trail of all your trades::

        # Daily incremental update (today only)
        n = export_order_history(
            api_key, secret, "orders.csv", past_n_days=0)

        # Back-fill on first run
        n = export_order_history(
            api_key, secret, "orders.csv", past_n_days=180)
        print(f"Saved {n} records")
    """
    filepath = Path(filepath) if isinstance(filepath, str) else filepath

    client = CryptoAPI(
        api_key=api_key,
        api_secret=secret_key,
        log_json_response_to_file=False,
        logs_directory="logs_trade",
    )

    # Download: today (i=0) then the past `past_n_days` calendar days (i=1…n)
    reference_date = datetime.date.today()
    all_data: list[TradeHistoryDataMessage] = []
    for i in range(0, past_n_days + 1):
        print(f"Getting trade history of past {i} days")
        day = reference_date - datetime.timedelta(days=i)
        data = client.get_all_trade_history_of_a_day(
            instrument_name=None, day=day
        )
        all_data.extend(data)

    df = pandas.DataFrame([item.model_dump() for item in all_data])
    df.drop_duplicates(subset="trade_id", keep="first", inplace=True)
    df.to_csv(filepath, index=False)
    return len(df)


def export_user_balance(
    api_key: str,
    secret_key: str,
    filepath: str | Path,
    pie_chart_filepath: str | Path | None = None,
    figsize: tuple[float | int, float | int] = (8, 8),
    filter_values_in_pie_chart: float = 1.0,
) -> None:
    """Export a snapshot of the current portfolio to a CSV file.

    Fetches the current account balance via the crypto.com API, saves it as
    a CSV, and optionally generates a pie chart of portfolio allocation by
    market value.

    Parameters
    ----------
    api_key:
        Your crypto.com API key.
    secret_key:
        Your crypto.com API secret.
    filepath:
        Destination path for the portfolio CSV snapshot.
    pie_chart_filepath:
        If given, a pie chart is saved to this path.  Matplotlib determines
        the format from the file extension (``".svg"``, ``".png"``, etc.).
        Pass ``None`` (default) to skip chart generation.
    figsize:
        Width and height in inches for the pie chart figure.  Default
        is ``(8, 8)``.
    filter_values_in_pie_chart:
        Minimum market value in USD for a currency to appear in the pie
        chart.  Positions at or below this threshold are excluded to avoid
        clutter from dust balances.  Default is ``1.0`` (hide balances
        worth $1 or less).

    When to use
    -----------
    Use to take a daily snapshot of your holdings.  The CSV can be compared
    across dates to track portfolio drift.  Combine with
    ``export_order_history`` in a scheduled job::

        export_user_balance(
            api_key, secret,
            filepath="portfolio.csv",
            pie_chart_filepath="portfolio.svg",
        )

    The CSV columns match those returned by
    :meth:`~crypto_dot_com.client.CryptoAPI.get_user_balance_summary_as_df`:
    ``symbol``, ``quantity``, ``market_value``, ``exchange``,
    ``portfolio_percentage``, ``date``.
    """
    filepath = Path(filepath) if isinstance(filepath, str) else filepath

    client = CryptoAPI(
        api_key=api_key,
        api_secret=secret_key,
        log_json_response_to_file=False,
    )

    df = client.get_user_balance_summary_as_df()
    if df is not None:
        df.to_csv(filepath, index=False)

    if pie_chart_filepath is None:
        return

    pie_chart_filepath = (
        Path(pie_chart_filepath)
        if isinstance(pie_chart_filepath, str)
        else pie_chart_filepath
    )

    portfolio = client.get_user_balance_summary()
    currencies = [
        item.symbol.base_currency.name
        for item in portfolio
        if item.market_value > filter_values_in_pie_chart
    ]
    market_values = [
        item.market_value
        for item in portfolio
        if item.market_value > filter_values_in_pie_chart
    ]

    fig, ax = plt.subplots(figsize=figsize)
    ax.pie(market_values, labels=currencies, autopct="%1.1f%%", startangle=140)
    ax.set_title("Portfolio Allocation")
    fig.savefig(pie_chart_filepath, dpi=300)
    plt.close(fig)
