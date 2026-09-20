"""One-off diagnostic: re-run QLoRA's full test-set evaluation with the fixed
non-greedy JSON parser (src/prompting.py's try_parse_json), to get the
real, gate-comparable exact_match_rate now that we know the old greedy
regex was discarding correct answers buried in repeated model output.

Uses the existing checkpoint on disk — no retraining involved.

Run:
    set -a; source .env; set +a
    .venv/bin/python3 full_qlora_reeval.py
"""
import json

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from src.evaluate import compute_metrics, run_predictions
from src.config import MODEL_NAME

ADAPTER_DIR = "outputs/qwen-qlora-run1/checkpoint-7885"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, quantization_config=bnb_config, device_map="auto"
)
model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
model.eval()

test_data = [json.loads(l) for l in open("data/processed/test.jsonl")]
print(f"Running generation on the full test set ({len(test_data)} examples)...", flush=True)

predictions = run_predictions(model, tokenizer, test_data)
metrics = compute_metrics(predictions)

print("\n=== QLoRA full test-set metrics (fixed parser) ===")
print(metrics)

with open("qlora_full_reeval_predictions.jsonl", "w") as f:
    for p in predictions:
        f.write(json.dumps(p) + "\n")
print("\nFull predictions written to qlora_full_reeval_predictions.jsonl")
