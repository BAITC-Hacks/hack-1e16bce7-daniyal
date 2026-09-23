"""Create append-import files from a synthetic profile, including its real history."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create(directory, employee_id):
    source = json.loads((ROOT / "dataset/employees.json").read_text(encoding="utf-8"))
    employee = next(row for row in source["employees"] if row["employee_id"] == "E0001")
    employee.update(employee_id=employee_id, full_name="Jury Browser Test")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "employees.json").write_text(json.dumps({**source, "employees": [employee]}, ensure_ascii=False), encoding="utf-8")
    with (ROOT / "dataset/activity_history.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        rows = [dict(row, employee_id=employee_id, record_id=f"{employee_id}-{row['record_id']}")
                for row in reader if row["employee_id"] == "E0001"]
    with (directory / "activity_history.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    print(create(args.directory, args.id))
