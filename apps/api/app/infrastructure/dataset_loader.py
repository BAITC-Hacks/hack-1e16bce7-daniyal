"""Read source files or HTTP uploads without changing the database."""
import csv
import io
import json
from pathlib import Path

from app.application.dataset import Dataset, HistoryRecord


def read_json(content: bytes, name: str):
    try:
        return json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as error:
        raise ValueError(f"{name}: invalid UTF-8 JSON") from error


def read_history(content: bytes) -> list[HistoryRecord]:
    try:
        source = io.StringIO(content.decode("utf-8-sig"), newline="")
    except UnicodeError as error:
        raise ValueError("activity_history.csv: invalid UTF-8") from error
    reader = csv.DictReader(source, strict=True)
    history = []
    try:
        if reader.fieldnames is None or len(reader.fieldnames) != len(HistoryRecord.model_fields) or set(reader.fieldnames) != set(HistoryRecord.model_fields):
            raise ValueError("activity_history.csv: unexpected CSV columns")
        for line, row in enumerate(reader, start=2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("unexpected CSV column count")
                for field in ("score", "feedback_rating", "due_date"):
                    row[field] = row[field] or None
                for field in ("score", "feedback_rating", "completion_pct"):
                    if row[field] is not None:
                        row[field] = int(row[field])
                history.append(HistoryRecord.model_validate(row))
            except (ValueError, TypeError) as error:
                raise ValueError(f"activity_history.csv:{line}: {error}") from error
    except csv.Error as error:
        raise ValueError(f"activity_history.csv:{reader.line_num}: malformed CSV") from error
    return history


def dataset_from_files(files: dict[str, bytes]) -> Dataset:
    return Dataset(catalog=read_json(files["skills.json"], "skills.json"),
                   employees=read_json(files["employees.json"], "employees.json"),
                   events=read_json(files["events.json"], "events.json"),
                   history=read_history(files["activity_history.csv"]))


def load_dataset(directory: Path) -> Dataset:
    return dataset_from_files({name: (directory / name).read_bytes() for name in
                               ("skills.json", "employees.json", "events.json", "activity_history.csv")})
