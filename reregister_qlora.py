"""Re-register the already-trained QLoRA checkpoint (outputs/qwen-qlora-run1/
checkpoint-7885) as a new ClearML model, this time with the output_uri fix
so weights are actually durably stored. No retraining, no new generation —
reuses the full-scale predictions already saved to
qlora_full_reeval_predictions.jsonl. Then re-applies promote.py's real
quality-gate/winner logic against the known-good LoRA production metrics
(logged directly by that run, unaffected by the parser bug since its
json_validity_rate was already 1.0) and promotes accordingly.
"""
import json

from src import promote
from src.clearml_utils import start_task
from src.config import configure_clearml_env, MODEL_NAME
from src.evaluate import compute_metrics

configure_clearml_env()

ADAPTER_DIR = "outputs/qwen-qlora-run1/checkpoint-7885"

# Recomputed from the saved full-test-set predictions — no GPU needed.
qlora_predictions = [json.loads(l) for l in open("qlora_full_reeval_predictions.jsonl")]
qlora_metrics = compute_metrics(qlora_predictions)
print("QLoRA metrics (recomputed from saved predictions):", qlora_metrics)

# Known-good, unaffected by the parser fix (json_validity_rate was already
# 1.0 for this run, so the fallback regex was never exercised).
lora_metrics = {
    "json_validity_rate": 1.0000,
    "exact_match_rate": 0.9801,
    "intent_accuracy": 0.9801,
    "urgency_accuracy": 0.9899,
    "category_accuracy": 0.9941,
}
base_metrics = {
    "json_validity_rate": 0.0,
    "exact_match_rate": 0.0,
    "intent_accuracy": 0.0,
    "urgency_accuracy": 0.0,
    "category_accuracy": 0.0,
}

task = start_task(
    "qwen0.5b-qlora-reregister",
    config={
        "model_name": MODEL_NAME,
        "method": "qlora",
        "note": "Re-registration of existing checkpoint-7885 after fixing "
                "(1) the output_uri storage bug and (2) the greedy-regex "
                "JSON parsing bug in try_parse_json. No retraining involved.",
        "source_checkpoint": ADAPTER_DIR,
    },
)

from clearml import OutputModel  # noqa: E402

output_model = OutputModel(task=task, name="qwen-ticket-extractor", framework="PyTorch")
output_model.update_weights(ADAPTER_DIR, async_enable=False)
output_model.tags = ["candidate", "qlora"]
print(f"Registered new QLoRA model: {output_model.id}")

from src.evaluate import log_metrics  # noqa: E402
log_metrics(task, base_metrics, "base")
log_metrics(task, qlora_metrics, "qlora")
task.close()

lora_passed, lora_reasons = promote.passes_quality_gate(lora_metrics, base_metrics)
qlora_passed, qlora_reasons = promote.passes_quality_gate(qlora_metrics, base_metrics)
print("LoRA (existing production) passes gate:", lora_passed, lora_reasons if not lora_passed else "")
print("QLoRA (new registration) passes gate:", qlora_passed, qlora_reasons if not qlora_passed else "")

from clearml import Model  # noqa: E402

candidates = []
if lora_passed:
    candidates.append(("lora", lora_metrics, Model(model_id="9a77f161b00a4b2583064f49eb91756f")))
if qlora_passed:
    candidates.append(("qlora", qlora_metrics, output_model))

winner = promote.pick_winner(candidates)
promote.promote(winner)

print("\n=== Final state ===")
print("New QLoRA model tags:", Model(model_id=output_model.id).tags)
print("Old LoRA production model tags:", Model(model_id="9a77f161b00a4b2583064f49eb91756f").tags)
print("New QLoRA model URL (should NOT be file:///tmp/...):", Model(model_id=output_model.id).url)
