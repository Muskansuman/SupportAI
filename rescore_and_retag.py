"""Re-score the actual paired LoRA (production) and QLoRA (rejected) models
from ClearML task cad65809.../48e98303... using the fixed non-greedy JSON
parser, then re-apply promote.py's real quality-gate/winner logic and
retag the ClearML registry accordingly. No retraining — pulls existing
registered weights.
"""
import json

import torch
from clearml import Model, Task
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src import promote
from src.config import configure_clearml_env, MODEL_NAME
from src.evaluate import compute_metrics, run_predictions

configure_clearml_env()

LORA_MODEL_ID = "9a77f161b00a4b2583064f49eb91756f"   # tags: lora, production
QLORA_MODEL_ID = "f09db191a87e44b8850c6a0c242355a8"  # tags: qlora, rejected, seed-42
LORA_TASK_ID = "cad65809a4c645eba21e8c3a5be3f365"
QLORA_TASK_ID = "48e98303a3e249d0aeaf90801642ad2c"

# base_metrics already confirmed genuine (base model never emits JSON at all,
# spot-checked separately) — reuse the values already logged in ClearML for
# this exact run rather than re-running the untuned base model.
BASE_METRICS = {
    "json_validity_rate": 0.0,
    "exact_match_rate": 0.0,
    "intent_accuracy": 0.0,
    "urgency_accuracy": 0.0,
    "category_accuracy": 0.0,
}

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

test_data = [json.loads(l) for l in open("data/processed/test.jsonl")]
print(f"Test set: {len(test_data)} examples\n", flush=True)


def eval_model(model, label):
    print(f"=== Running generation for {label} ===", flush=True)
    predictions = run_predictions(model, tokenizer, test_data)
    metrics = compute_metrics(predictions)
    print(f"{label} metrics (fixed parser): {metrics}\n", flush=True)
    return metrics


# --- LoRA (production) ---
lora_adapter_dir = Model(model_id=LORA_MODEL_ID).get_local_copy()
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, torch_dtype=torch.bfloat16, device_map="auto"
)
lora_model = PeftModel.from_pretrained(base_model, lora_adapter_dir)
lora_model.eval()
lora_metrics = eval_model(lora_model, "LoRA (production)")
del lora_model, base_model
torch.cuda.empty_cache()

# --- QLoRA (rejected) ---
qlora_adapter_dir = Model(model_id=QLORA_MODEL_ID).get_local_copy()
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
qbase_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, quantization_config=bnb_config, device_map="auto"
)
qlora_model = PeftModel.from_pretrained(qbase_model, qlora_adapter_dir)
qlora_model.eval()
qlora_metrics = eval_model(qlora_model, "QLoRA (rejected)")
del qlora_model, qbase_model
torch.cuda.empty_cache()

# --- Re-apply the real quality gate ---
lora_passed, lora_reasons = promote.passes_quality_gate(lora_metrics, BASE_METRICS)
qlora_passed, qlora_reasons = promote.passes_quality_gate(qlora_metrics, BASE_METRICS)
print("LoRA passes gate:", lora_passed, "| Reasons:", lora_reasons if not lora_passed else "N/A")
print("QLoRA passes gate:", qlora_passed, "| Reasons:", qlora_reasons if not qlora_passed else "N/A")

lora_output_model = Model(model_id=LORA_MODEL_ID)
qlora_output_model = Model(model_id=QLORA_MODEL_ID)

candidates = []
if lora_passed:
    candidates.append(("lora", lora_metrics, lora_output_model))
if qlora_passed:
    candidates.append(("qlora", qlora_metrics, qlora_output_model))

winner = promote.pick_winner(candidates)

print("\n=== Current tags before retagging ===")
print("LoRA:", lora_output_model.tags)
print("QLoRA:", qlora_output_model.tags)

if winner and winner[0] != "lora":
    print(f"\nWinner changed to '{winner[0]}' — retagging ClearML registry...")
    promote.promote(winner)
    promote.reject_losers(
        {"lora": lora_output_model, "qlora": qlora_output_model},
        winner_name=winner[0],
    )
elif winner and winner[0] == "lora":
    print("\nLoRA remains the winner — no retagging needed.")
else:
    print("\nNo candidate passed the gate — no retagging performed.")

print("\n=== Final tags ===")
print("LoRA:", Model(model_id=LORA_MODEL_ID).tags)
print("QLoRA:", Model(model_id=QLORA_MODEL_ID).tags)
