import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUTS_DIR = ROOT_DIR / "outputs"
RAW_TICKETS_PATH = DATA_RAW_DIR / "raw_tickets.jsonl"

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"  # swap to 1.5B later for comparison
CLEARML_PROJECT_NAME = "openllmops"
MODEL_REGISTRY_NAME = "qwen-ticket-extractor"
SUPPORT_MODEL_REGISTRY_NAME = "supportai-fashion-classifier"

# Ensure required directories exist so downstream code (dataset loading,
# TrainingArguments output_dir, adapter saving) never fails on a missing path.
for _dir in (DATA_RAW_DIR, DATA_PROCESSED_DIR, OUTPUTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def configure_clearml_env():
    """Point the clearml SDK at the ClearML server, reading credentials from
    the environment (see .env.example — populate a real .env, never commit one).
    """
    os.environ.setdefault("CLEARML_WEB_HOST", "https://app.clear.ml/")
    os.environ.setdefault("CLEARML_API_HOST", "https://api.clear.ml")
    os.environ.setdefault("CLEARML_FILES_HOST", "https://files.clear.ml")

    access_key = os.environ.get("CLEARML_API_ACCESS_KEY")
    secret_key = os.environ.get("CLEARML_API_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError(
            "CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY are not set. "
            "Copy .env.example to .env, fill in your ClearML credentials, and "
            "load it (e.g. `set -a; source .env; set +a`) before running."
        )