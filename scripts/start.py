"""One-command demo bootstrap. Requires Python 3.10+ and Docker Compose v2."""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_env(path):
    result = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)$", line)
            if match:
                result[match[1]] = match[2].strip().strip("\"'")
    return result


def configure(path, args):
    """Preserve existing credentials and unrelated settings; enable demo access."""
    original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    values = read_env(path)
    updates = {"DEMO_AUTH_ENABLED": "true"}
    defaults = {"POSTGRES_DB": "career_quest", "POSTGRES_USER": "career_quest",
                "POSTGRES_PASSWORD": secrets.token_hex(24),
                "JWT_SECRET": secrets.token_hex(32), "DEMO_HR_PASSWORD": secrets.token_hex(16),
                "WEB_BIND_HOST": "127.0.0.1", "API_BIND_HOST": "127.0.0.1",
                "WEB_PORT": "3000", "API_PORT": "8000", "POSTGRES_PORT": "55432",
                "LLM_PROVIDER": "openai", "LLM_ENABLED": "true",
                "OLLAMA_MODEL": "qwen3:8b", "OLLAMA_TIMEOUT_SECONDS": "6"}
    for key, value in defaults.items():
        if not values.get(key):
            updates[key] = value
    for key, value in (("WEB_PORT", args.web_port), ("API_PORT", args.api_port),
                       ("POSTGRES_PORT", args.db_port)):
        if value is not None:
            updates[key] = str(value)
    if args.gpu:
        updates.update(LLM_PROVIDER="ollama", LLM_ENABLED="true")
    # Replace exact assignments, preserving comments and all unrelated entries.
    lines = []
    remaining = dict(updates)
    for line in original.splitlines():
        key = line.split("=", 1)[0].strip()
        if key in updates:
            if key in remaining:
                lines.append(f"{key}={remaining.pop(key)}")
        else:
            lines.append(line)
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    # Restrict new secret files on Unix; existing permissions remain unchanged.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")
    return values | updates


def port(value):
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return number


def main(argv=None, runner=subprocess.run):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", action="store_true", help="Download and start Qwen on an NVIDIA GPU")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--project", help="Separate Compose project and persistent volumes")
    parser.add_argument("--web-port", type=port)
    parser.add_argument("--api-port", type=port)
    parser.add_argument("--db-port", type=port)
    args = parser.parse_args(argv)
    env_path = args.env_file.resolve()
    # Fail before changing configuration if Docker is unavailable.
    runner(["docker", "info", "--format", "{{.ServerVersion}}"], check=True, cwd=ROOT)
    runner(["docker", "compose", "version"], check=True, cwd=ROOT)
    values = configure(env_path, args)
    compose = ["docker", "compose", "--env-file", str(env_path), "-f", str(ROOT / "compose.yaml")]
    if args.project:
        compose += ["--project-name", args.project]
    # Explicit env-file values take precedence over an unrelated calling shell.
    environment = dict(os.environ)
    for key in values:
        environment.pop(key, None)
    gpu = values.get("LLM_PROVIDER") == "ollama"
    if gpu:
        compose += ["--profile", "gpu"]

    def run(*command):
        runner(compose + list(command), check=True, cwd=ROOT, env=environment)

    run("config", "--quiet")
    run("build", "api", "web")
    run("up", "-d", "--wait", "--wait-timeout", "180", "db")
    run("run", "--rm", "--no-deps", "api", "alembic", "upgrade", "head")
    run("run", "--rm", "--no-deps", "--volume", f"{ROOT / 'dataset'}:/dataset:ro",
        "api", "python", "-m", "app.import_dataset", "/dataset")
    if gpu:
        run("up", "-d", "--wait", "--wait-timeout", "180", "ollama")
        run("exec", "-T", "ollama", "ollama", "pull", values["OLLAMA_MODEL"])
    run("up", "-d", "--wait", "--wait-timeout", "180", "api", "web")
    print(f"\nReady: http://localhost:{values['WEB_PORT']}")
    print(f"HR login: DEMO_HR_PASSWORD in {env_path} (not printed to logs).")
    if gpu:
        print("Qwen downloaded; API warms it in the background. Timeouts use labelled template explanations.")
    elif not values.get("OPENAI_API_KEY"):
        print("No model key configured: grounded template explanations are enabled.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Startup stopped ({type(error).__name__}). See the failed step above; existing volumes were kept.", file=sys.stderr)
        sys.exit(1)
