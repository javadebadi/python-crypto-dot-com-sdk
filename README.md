# Python Crypto.com SDK

A Python wrapper for the [crypto.com Exchange REST API v1](https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html).

## Installation

```bash
pip install python_crypto_dot_com_sdk
```

## Setup

All private endpoints (trading, account balance, order history) require an API key and secret from your crypto.com Exchange account.

```python
from crypto_dot_com.client import CryptoAPI

client = CryptoAPI(
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
)
```

**Optional parameters:**

| Parameter | Default | Description |
|---|---|---|
| `timeout` | `1000` | Request timeout in ms |
| `log_json_response_to_file` | `False` | Save raw API responses as JSON files |
| `logs_directory` | `None` | Directory for JSON logs (current dir if `None`) |

Enable response logging when debugging or auditing API calls:

```python
client = CryptoAPI(
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
    log_json_response_to_file=True,
    logs_directory="logs/",
)
```

---

## Market Data

Market data is public — no API credentials are required.

### Get recent candlesticks

Use this to fetch the most recent OHLCV (Open, High, Low, Close, Volume) candles for a trading pair. Suitable for displaying a price chart or feeding a real-time strategy.

```python
candles = client.get_candlesticks(
    instrument_name="BTC_USD",
    timeframe="1h",   # see intervals below
    count=100,        # number of candles (max 300)
)

for c in candles:
    print(c.datetime, c.open, c.high, c.low, c.close, c.volume)
```

**Available timeframes** (`CandlestickTimeInterval`):

| Value | Enum name | Period |
|---|---|---|
| `"1m"` | `MIN_1` | 1 minute |
| `"5m"` | `MIN_5` | 5 minutes |
| `"15m"` | `MIN_15` | 15 minutes |
| `"30m"` | `MIN_30` | 30 minutes |
| `"1h"` | `HOUR_1` | 1 hour |
| `"2h"` | `HOUR_2` | 2 hours |
| `"4h"` | `HOUR_4` | 4 hours |
| `"12h"` | `HOUR_12` | 12 hours |
| `"1D"` | `DAY_1` | 1 day |
| `"7D"` | `DAY_7` | 7 days |
| `"14D"` | `DAY_14` | 14 days |
| `"1M"` | `MONTH_1` | 1 month |

### Download full historical candlestick data

Use this to build a local dataset for backtesting or analysis. The method automatically walks backwards in time, making repeated API calls until no more data is available (or until `min_datetime` is reached).

```python
import datetime
import pytz

candles = client.get_all_candlesticks(
    instrument_name="BTC_USD",
    interval="1D",                        # daily candles
    verbose=True,                         # print progress
)

# Limit the date range
candles = client.get_all_candlesticks(
    instrument_name="ETH_USD",
    interval="1h",
    min_datetime=datetime.datetime(2024, 1, 1, tzinfo=pytz.UTC),
    max_datetime=datetime.datetime(2024, 6, 1, tzinfo=pytz.UTC),
    verbose=False,
)

# Save to JSON
import json
with open("btc_daily.json", "w") as f:
    json.dump([c.model_dump() for c in candles], f, indent=2, default=str)
```

> **When to use `get_candlesticks` vs `get_all_candlesticks`:**
> - `get_candlesticks` — live dashboards, recent data, or when you know the exact time window.
> - `get_all_candlesticks` — one-time historical downloads or building a full dataset for backtesting.

---

## Portfolio & Balance

### View your current holdings

Returns your portfolio as a list of positions, one per currency held.

```python
# As a list of xarizmi PortfolioItem objects
items = client.get_user_balance_summary()
for item in items:
    print(item.symbol.base_currency.name, item.quantity, item.market_value)

# As a xarizmi Portfolio object (useful with the xarizmi ecosystem)
portfolio = client.get_current_portfolio()

# As a pandas DataFrame (useful for quick analysis or export)
df = client.get_user_balance_summary_as_df()
print(df[["symbol", "market_value", "portfolio_percentage"]])
```

The DataFrame is sorted by `market_value` descending and includes:

| Column | Description |
|---|---|
| `symbol` | Currency name (e.g. `BTC`) |
| `quantity` | Amount held |
| `market_value` | USD market value |
| `exchange` | Always `crypto.com` |
| `portfolio_percentage` | Fraction of total portfolio (0–1) |
| `date` | Today's date |

Optional flags:
```python
df = client.get_user_balance_summary_as_df(
    include_portfolio_percentage=False,
    include_date=False,
)
```

> **Use `get_user_balance_summary_as_df`** when you want to quickly inspect or export your holdings. Use `get_current_portfolio` when integrating with the xarizmi framework (e.g. for portfolio ratio analysis).

---

## Order Management

### Place a limit buy order

A limit order lets you specify the exact price at which you want to buy. The order sits in the order book until it is filled or cancelled.

```python
# Returns a simple object with order_id and client_oid
order = client.create_limit_order(
    instrument_name="CRO_USD",
    quantity=1000,
    side="BUY",
    price=0.12,
)
print(order.order_id)

# Returns a xarizmi Order (preferred when using the xarizmi ecosystem)
order = client.create_buy_limit_order_xarizmi(
    instrument_name="CRO_USD",
    quantity=1000,
    price=0.12,
)
```

### Place a limit sell order

```python
order = client.create_sell_limit_order_xarizmi(
    instrument_name="CRO_USD",
    quantity=1000,
    price=0.15,
)
```

> **`create_limit_order` vs `create_buy/sell_limit_order_xarizmi`:**
> - `create_limit_order` returns only the `order_id` and `client_oid` from the API response. Use it when you just need to fire and record the ID.
> - `create_buy_limit_order_xarizmi` / `create_sell_limit_order_xarizmi` return a fully populated xarizmi `Order` object (with symbol, price, quantity, side, and status). Use these when you want to track the order in your own data model.

### Cancel orders

```python
# Cancel a specific order
client.cancel_order(order_id="11111000000000000001")

# Cancel all open orders for an instrument (asynchronous — confirmation only)
client.cancel_all_orders(instrument_name="CRO_USD")

# Cancel all open orders across all instruments
client.cancel_all_orders()
```

> **Note:** `cancel_all_orders` is asynchronous on the exchange side. The call returns immediately after the request is accepted, not after the orders are actually cancelled. Wait briefly and check order status if you need confirmation.

### Error handling for order placement

The API returns specific error codes that are mapped to Python exceptions:

```python
from crypto_dot_com.exceptions import BadPriceException, BadQuantityException

try:
    client.create_limit_order("CRO_USD", quantity=1000, side="BUY", price=0.0)
except BadPriceException:
    print("Price was rejected by the exchange (too low, too high, or zero)")
except BadQuantityException:
    print("Quantity was rejected (below minimum or invalid)")
except RuntimeError as e:
    print(f"Unexpected API error: {e}")
```

---

## Order History & Status

### Check the status of a specific order

Use this to poll whether an order has been filled, is still active, or was cancelled. Common in automated trading loops.

```python
# Raw response (crypto.com data model)
order = client.get_order_details(order_id="11111000000000000001")
print(order.status)          # ACTIVE | FILLED | CANCELED | REJECTED | EXPIRED
print(order.avg_price)       # average fill price
print(order.cumulative_quantity)  # how much has been filled so far

# xarizmi Order (maps status to xarizmi OrderStatusEnum)
order = client.get_order_details_in_xarizmi(order_id="11111000000000000001")
print(order.status)   # OrderStatusEnum.ACTIVE | DONE | CANCELLED
print(order.price)    # computed as order_value / quantity
```

### Fetch order history for a time range

Use this to review what trades were executed. The client automatically handles pagination — if the API returns the maximum number of records, it splits the time range and recurses until all orders are retrieved.

```python
# Timestamps in nanoseconds
orders = client.get_order_history(
    start_time=1_704_067_200_000_000_000,
    end_time=1_704_153_600_000_000_000,
    instrument_name="BTC_USD",   # omit to get all instruments
)

# Convenience wrapper for a single calendar day
import datetime
orders = client.get_all_order_history_of_a_day(
    day=datetime.date(2024, 6, 15),
    instrument_name="CRO_USD",
)

for o in orders:
    print(o.order_id, o.side, o.status, o.avg_price, o.cumulative_quantity)
```

> **Limit:** Crypto.com allows retrieving order history up to **6 months** in the past. Run `export_order_history` (see below) regularly to maintain a longer local record.

---

## Export Utilities

The `crypto_dot_com.export` module provides standalone functions for downloading and persisting data without managing a `CryptoAPI` instance directly.

### Export order history to CSV

Downloads order history and saves it to a CSV file. If the file already exists, new records are merged and duplicates (by `order_id`) are removed — so you can run this daily as an incremental update.

```python
from crypto_dot_com.export import export_order_history

# Download today's orders and append to existing file
n_records = export_order_history(
    api_key="YOUR_API_KEY",
    secret_key="YOUR_API_SECRET",
    filepath="orders.csv",
    past_n_days=0,     # 0 = today only; 7 = today + last 7 days
)
print(f"Total records in file: {n_records}")
```

### Read and filter a saved CSV

```python
from crypto_dot_com.export import read_order_history_from_csv
from crypto_dot_com.enums import StatusEnum

# Load as list of OrderHistoryDataMessage objects
orders = read_order_history_from_csv(
    filepath="orders.csv",
    filter_by_status=[StatusEnum.FILLED],
    filter_by_instrument_name="BTC_USD",
)

# Load as a DataFrame instead
df = read_order_history_from_csv(
    filepath="orders.csv",
    filter_by_status=["FILLED", "CANCELED"],
    return_type="dataframe",
)
```

### Export portfolio snapshot to CSV and pie chart

Takes a snapshot of your current holdings and saves it to CSV. Optionally generates a pie chart of your portfolio allocation.

```python
from crypto_dot_com.export import export_user_balance

export_user_balance(
    api_key="YOUR_API_KEY",
    secret_key="YOUR_API_SECRET",
    filepath="portfolio.csv",
    pie_chart_filepath="portfolio.svg",   # omit to skip the chart
    figsize=(10, 10),
)
```

> **Tip:** Schedule `export_order_history` and `export_user_balance` to run daily (e.g. with cron or a scheduler) to build a long-term record of your trading activity and portfolio performance.

---

## Instrument names

Crypto.com uses `BASE_QUOTE` format for instrument names:

```
BTC_USD    — Bitcoin priced in USD
ETH_USDT   — Ethereum priced in USDT
CRO_USD    — Cronos priced in USD
```

Pass these strings as-is to any method that accepts `instrument_name`.

---

## Integration with xarizmi

Methods suffixed with `_xarizmi` return objects from the [xarizmi](https://github.com/javadebadi/xarizmi) framework, which provides a unified data model for portfolio management across exchanges. Use these when you want to:

- Compare portfolios across exchanges
- Use xarizmi's portfolio ratio analysis (`portfolio / past_portfolio`)
- Store orders and candles in xarizmi's database via `CryptoDbApiClient` (see `crypto_dot_com/client_db.py`)
