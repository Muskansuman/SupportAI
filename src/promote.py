"""Quality gate + promotion logic: decide whether a LoRA/QLoRA candidate is
good enough to become the "production"-tagged model in the ClearML registry.
"""
from clearml import Model

from src.config import CLEARML_PROJECT_NAME, MODEL_REGISTRY_NAME

# Tune these thresholds based on what a given eval run's comparison table shows.
MIN_JSON_VALIDITY = 0.90          # candidate must produce valid JSON at least 90% of the time
MIN_EXACT_MATCH = 0.50            # candidate must get all 3 fields fully correct at least 50% of the time
MIN_IMPROVEMENT_OVER_BASE = 0.10  # must beat base model's exact_match by at least this margin


def passes_quality_gate(metrics, base_metrics):
    reasons = []
    passed = True

    if metrics["json_validity_rate"] < MIN_JSON_VALIDITY:
        passed = False
        reasons.append(f"json_validity_rate {metrics['json_validity_rate']:.2f} < {MIN_JSON_VALIDITY}")

    if metrics["exact_match_rate"] < MIN_EXACT_MATCH:
        passed = False
        reasons.append(f"exact_match_rate {metrics['exact_match_rate']:.2f} < {MIN_EXACT_MATCH}")

    improvement = metrics["exact_match_rate"] - base_metrics["exact_match_rate"]
    if improvement < MIN_IMPROVEMENT_OVER_BASE:
        passed = False
        reasons.append(f"improvement over base {improvement:.2f} < {MIN_IMPROVEMENT_OVER_BASE}")

    return passed, reasons


def pick_winner(candidates):
    """candidates: list of (name, metrics, output_model) tuples that passed the gate.
    Prefers the higher exact_match_rate; ties favor whichever sorts first
    (QLoRA is listed after LoRA by convention, so equal scores favor LoRA).
    """
    if not candidates:
        print("No candidate passed the quality gate. Nothing promoted.")
        return None
    winner = max(candidates, key=lambda c: c[1]["exact_match_rate"])
    print(f"Winner: {winner[0]} (exact_match_rate={winner[1]['exact_match_rate']:.3f})")
    return winner


def promote(winner):
    if not winner:
        print("No promotion performed — check quality gate thresholds or retrain with more data.")
        return

    winner_name, _, winner_output_model = winner

    existing_production_models = Model.query_models(
        project_name=CLEARML_PROJECT_NAME,
        model_name=MODEL_REGISTRY_NAME,
        tags=["production"],
    )
    for m in existing_production_models:
        m.tags = [t for t in m.tags if t != "production"] + ["archived"]
        print(f"Archived previous production model: {m.id}")

    winner_output_model.tags = [t for t in winner_output_model.tags if t != "candidate"] + ["production"]
    print(f"Promoted '{winner_name}' model to production")
    print(f"   Model ID: {winner_output_model.id}")


def reject_losers(all_candidate_models, winner_name):
    """all_candidate_models: {method_name: output_model}. Tags every entry
    other than winner_name as 'rejected', keeping the registry self-documenting.
    """
    for name, m in all_candidate_models.items():
        if name == winner_name:
            continue
        m.tags = [t for t in m.tags if t != "candidate"] + ["rejected"]
        print(f"Tagged '{name}' model as rejected")


def get_production_weights():
    production_models = Model.query_models(
        project_name=CLEARML_PROJECT_NAME,
        model_name=MODEL_REGISTRY_NAME,
        tags=["production"],
    )
    if not production_models:
        raise ValueError("No production model found — run promote() first")

    production_model = production_models[0]
    weights_path = production_model.get_local_copy()
    print(f"Pulled production model weights to: {weights_path}")
    print(f"   Model tags: {production_model.tags}")
    return production_model, weights_path
