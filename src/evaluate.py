"""Evaluate a model on the held-out test set: JSON validity rate and
per-field accuracy against expected {intent, urgency, category} labels.
"""
import json

import pandas as pd
import torch
from transformers import AutoModelForCausalLM

from src.config import MODEL_NAME
from src.prompting import generate_prediction, try_parse_json


def load_test_data(dataset_path):
    test_data = [json.loads(line) for line in open(f"{dataset_path}/test.jsonl")]
    print(f"Loaded {len(test_data)} test examples")
    return test_data


def load_base_model_for_eval():
    """Load a clean, non-fine-tuned copy of the base model for comparison."""
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, torch_dtype=torch.bfloat16, device_map="auto"
    )
    base_model.eval()
    return base_model


def run_predictions(model, tokenizer, test_data):
    model.eval()
    predictions = []
    for example in test_data:
        pred_text = generate_prediction(model, tokenizer, example["instruction"], example["input"])
        predictions.append({
            "input": example["input"],
            "expected": example["output"],
            "predicted_raw": pred_text,
            "predicted_parsed": try_parse_json(pred_text),
        })
    return predictions


def compute_metrics(predictions, fields=("intent", "urgency", "category")):
    total = len(predictions)
    valid_json_count = 0
    field_correct = {f: 0 for f in fields}
    fully_correct = 0

    for p in predictions:
        parsed = p["predicted_parsed"]
        if parsed is not None:
            valid_json_count += 1
            all_fields_correct = True
            for f in fields:
                if parsed.get(f) == p["expected"].get(f):
                    field_correct[f] += 1
                else:
                    all_fields_correct = False
            if all_fields_correct:
                fully_correct += 1

    metrics = {
        "json_validity_rate": valid_json_count / total,
        "exact_match_rate": fully_correct / total,
    }
    for f in fields:
        metrics[f"{f}_accuracy"] = field_correct[f] / total
    return metrics


def log_metrics(task, metrics, prefix):
    """Log metrics onto a ClearML task's 'eval_comparison' scalar plot."""
    logger = task.get_logger()
    for k, v in metrics.items():
        logger.report_scalar(title="eval_comparison", series=f"{prefix}_{k}", value=v, iteration=0)


def compare(base_metrics, lora_metrics, qlora_metrics):
    comparison_df = pd.DataFrame({"base": base_metrics, "lora": lora_metrics, "qlora": qlora_metrics}).T
    print(comparison_df)
    return comparison_df
