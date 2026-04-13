import os

from app.api import app


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    debug = _env_flag("TRANSACTIQ_DEBUG", "0")
    app.run(host="0.0.0.0", port=5000, debug=debug)
