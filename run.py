import os


def main() -> None:
    """Launch Gunicorn the same way we do in the Dockerfile for local dev.

    This avoids importing the FastAPI app in the parent process, so no DB
    connections are opened before Gunicorn forks its workers (prevents SSL
    errors when using Railway/PostgreSQL).
    """

    host = os.getenv("HOST", "0.0.0.0")
    port = os.getenv("PORT", "8000")
    reload = os.getenv("RELOAD", "false").lower() == "true"

    # Optional: let caller override the number of Gunicorn workers
    workers_env = os.getenv("WORKERS")  # e.g. WORKERS=10

    cmd = [
        "gunicorn",
        "app.main:app",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "--bind",
        f"{host}:{port}",
        "--log-level",
        "info",
    ]

    if reload:
        cmd.append("--reload")

    # Inject --workers flag if WORKERS env var is set
    if workers_env and workers_env.isdigit():
        cmd.extend(["--workers", workers_env])

    # Replace the current process with Gunicorn.
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
