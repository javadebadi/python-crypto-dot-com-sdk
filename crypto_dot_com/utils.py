import csv
import json
import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from pydantic import BaseModel


def get_current_time_ms() -> int:
    """Returns current unix timestamp in milliseconds

    Returns
    -------
    int
    """
    return int(time.time() * 1000)


def get_current_time_ns() -> int:
    """Returns current unix timestamp in nanoseconds

    Returns
    -------
    int
    """
    return int(time.time_ns())


def get_current_time_ms_as_string() -> str:
    """Returns current unix timestamp in milliseconds as string.

    Returns
    -------
    str
    """
    return f"{get_current_time_ms()}"


def json_to_file(obj: dict[Any, Any] | list[Any], filepath: str) -> None:
    with open(filepath, "w") as f:
        json.dump(obj, f, indent=4)


def sort_dict_by_key(d: dict[str, Any]) -> dict[str, Any]:
    return dict(sorted(d.items()))


def models_to_csv(models: list[BaseModel], file_path: str) -> None:
    # Convert models to a list of dictionaries
    data = [model.model_dump() for model in models]

    # Use csv.DictWriter to write the list of dictionaries to a CSV file
    if data:
        with open(file_path, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)


def get_day_timestamps(
    days_before: int, reference_date: date | None = None
) -> tuple[int, int]:
    """Returns unix start timestamp and end timestamp of given
    day in nano seconds"""
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    # Calculate the target date by subtracting the specified number of days
    target_date = reference_date - timedelta(days=days_before)

    # Define the start and end of the target day in UTC
    start_of_day = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )
    end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)

    # Return the timestamps
    return int(start_of_day.timestamp() * 1e9), int(
        end_of_day.timestamp() * 1e9
    )
