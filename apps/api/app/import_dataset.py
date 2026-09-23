"""Usage: python -m app.import_dataset ../../dataset [--validate-only]."""
import argparse
import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.application.import_dataset import import_dataset
from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.dataset_loader import load_dataset


def main():
    parser = argparse.ArgumentParser(description="Validate and atomically import a Career Quest dataset")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.directory)
        if args.validate_only:
            print(json.dumps({"status": "valid", "skills": len(dataset.catalog.skills),
                "employees": len(dataset.employees.employees), "events": len(dataset.events.events),
                "history": len(dataset.history)}))
            return
        database = Database(Settings().database_url)
        try:
            with database.sessions() as session:
                print(json.dumps(import_dataset(session, dataset)))
        finally:
            database.close()
    except (ValueError, OSError) as error:
        parser.exit(1, f"Import failed: {error}\n")
    except SQLAlchemyError:
        parser.exit(1, "Import failed: database error; check connectivity and run alembic upgrade head\n")


if __name__ == "__main__":
    main()
