import csv
import json
from typing import Any

from pydantic import BaseModel


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
