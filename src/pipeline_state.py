"""Tiny on-disk state file so `run_pipeline.py` can resume after a crash
instead of rebuilding the dataset and retraining already-finished stages.

Stages write their result into this file as soon as they finish (dataset
registration; LoRA train+eval; QLoRA train+eval). A rerun loads it, skips
any stage already present, and continues from whichever stage is missing.
Delete outputs/pipeline_state.json (or pass --fresh) to start clean.
"""
import json

from src.config import OUTPUTS_DIR

STATE_PATH = OUTPUTS_DIR / "pipeline_state.json"


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def clear_state():
    if STATE_PATH.exists():
        STATE_PATH.unlink()
