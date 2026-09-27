"""Credential loading and persistent-storage paths.

The Apify token comes from an environment variable or the .env file (env wins).
The persistent base dir (brand/ + research/) is resolved by `content_home()`.
"""

import os
from pathlib import Path

ENV_PATH = Path.home() / ".config" / "content" / ".env"
APIFY_KEY_NAME = "APIFY_TOKEN"
CONTENT_HOME_VAR = "CONTENT_HOME"
DEFAULT_CONTENT_HOME = Path.home() / "Documents" / "Content"


def content_home():
    """Resolve the persistent base dir holding brand/ and research/.

    Honors the CONTENT_HOME env var; defaults to ~/Documents/Content. This is
    deliberately NOT the current working directory: the skill is invoked from
    anywhere and runs daily, so brand/ (the user's identity) and research/ (the
    dated history that feeds taste memory) must be found again on the next run
    regardless of where the terminal happens to be.
    """
    override = os.environ.get(CONTENT_HOME_VAR, "").strip()
    return Path(override).expanduser() if override else DEFAULT_CONTENT_HOME


def _read_key(name, env_path=ENV_PATH):
    """Return `name` from the environment (wins) or the .env file ('' if none)."""
    value = os.environ.get(name, "")
    if value:
        return value
    if env_path and Path(env_path).exists():
        for line in Path(env_path).read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def load_apify_token(env_path=ENV_PATH):
    """Return the Apify token from the env var or .env file ('' if none)."""
    return _read_key(APIFY_KEY_NAME, env_path)


def active_backend(env_path=ENV_PATH):
    """Resolve the scraper backend and its credential.

    Returns (backend, credential): ("apify", token) when APIFY_TOKEN is present,
    else (None, "").
    """
    token = load_apify_token(env_path)
    if token:
        return "apify", token
    return None, ""
