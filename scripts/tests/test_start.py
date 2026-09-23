import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("bootstrap", Path(__file__).parents[1] / "start.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTest(unittest.TestCase):
    def test_repeated_start_keeps_credentials_and_orders_initialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = Path(temporary) / ".env"
            env.write_text("POSTGRES_PASSWORD=keep-database-password\n# custom\nOTHER=value\n", encoding="utf-8")
            calls = []
            run = lambda command, **kwargs: calls.append(command)
            bootstrap.main(["--env-file", str(env), "--gpu", "--project", "jury"], runner=run)
            first = bootstrap.read_env(env)
            bootstrap.main(["--env-file", str(env)], runner=run)
            self.assertEqual(first, bootstrap.read_env(env))
            self.assertEqual(first["POSTGRES_PASSWORD"], "keep-database-password")
            self.assertEqual(first["OTHER"], "value")
            self.assertGreaterEqual(len(first["JWT_SECRET"]), 32)
            commands = [" ".join(command) for command in calls]
            index = lambda fragment: next(i for i, command in enumerate(commands) if fragment in command)
            self.assertLess(index("alembic upgrade head"), index("app.import_dataset"))
            self.assertLess(index("app.import_dataset"), index("ollama pull"))
            self.assertLess(index("ollama pull"), index("180 api web"))

    def test_failed_migration_prevents_import_and_service_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if "alembic" in command:
                    raise subprocess.CalledProcessError(1, command)
            with self.assertRaises(subprocess.CalledProcessError):
                bootstrap.main(["--env-file", str(Path(temporary) / ".env")], runner=run)
            self.assertFalse(any("app.import_dataset" in command for command in calls))
            self.assertFalse(any(command[-2:] == ["api", "web"] and "up" in command for command in calls))


if __name__ == "__main__":
    unittest.main()
