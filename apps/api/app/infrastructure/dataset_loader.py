"""Read the official files without making changes to the database."""
import csv
import json
from pathlib import Path

from app.application.dataset import Dataset, HistoryRecord


def load_dataset(directory: Path) -> Dataset:
    def read(name):
        with (directory / name).open(encoding="utf-8-sig") as source:
            return json.load(source)

    history = []
    with (directory / "activity_history.csv").open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or set(reader.fieldnames) != set(HistoryRecord.model_fields):
            raise ValueError("activity_history.csv: unexpected CSV columns")
        for line, row in enumerate(reader, start=2):
            try:
                for field in ("score", "feedback_rating", "due_date"):
                    row[field] = row[field] or None
                for field in ("score", "feedback_rating", "completion_pct"):
                    if row[field] is not None:
                        row[field] = int(row[field])
                history.append(HistoryRecord.model_validate(row))
            except (ValueError, TypeError) as error:
                raise ValueError(f"activity_history.csv:{line}: {error}") from error
    return Dataset(catalog=read("skills.json"), employees=read("employees.json"),
                   events=read("events.json"), history=history)
