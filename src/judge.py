"""LLM-as-judge diagnostics for exact-match failures.

Ground truth for this task is categorical ({intent, urgency, category}), so
exact-match against it stays the authoritative metric and the quality gate
in promote.py. This module only explains *why* a prediction already failed
exact-match — truncated output, malformed JSON, a genuinely wrong label,
etc. — using a bigger Qwen2.5 model as judge. Diagnostic only: nothing here
feeds back into passes_quality_gate() or pick_winner().
"""
import json
import random

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.prompting import try_parse_json

JUDGE_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

FAILURE_TAXONOMY = [
    "truncated_output",       # cut off before the JSON object closed
    "malformed_json",         # not truncated, but syntactically invalid JSON
    "extra_text",             # valid JSON present, but wrapped in extra prose
    "wrong_label",            # valid, well-formed JSON with an incorrect field value
    "hallucinated_fields",    # valid JSON but with unexpected/extra/missing keys
    "other",
]

_JUDGE_INSTRUCTIONS = f"""You are diagnosing why a small model failed at a support-ticket \
classification task. The model was supposed to read a customer message and output JSON \
matching {{"intent": ..., "urgency": ..., "category": ...}}.

Given the customer message, the expected correct JSON, and the model's actual raw output, \
pick exactly one failure_type from this list: {", ".join(FAILURE_TAXONOMY)}.

Respond with only a JSON object: {{"failure_type": "<one of the list above>", "reasoning": \
"<one short sentence>"}}"""


def load_judge_model():
    tokenizer = AutoTokenizer.from_pretrained(JUDGE_MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        JUDGE_MODEL_NAME, torch_dtype=torch.bfloat16, device_map="auto"
    )
    model.eval()
    return model, tokenizer


def build_judge_prompt(input_text, expected, predicted_raw):
    return (
        f"{_JUDGE_INSTRUCTIONS}\n\n"
        f"Customer message: {input_text}\n"
        f"Expected JSON: {json.dumps(expected)}\n"
        f"Model's raw output: {predicted_raw!r}\n"
    )


def diagnose_prediction(judge_model, judge_tokenizer, prediction, max_new_tokens=60):
    prompt = build_judge_prompt(
        prediction["input"], prediction["expected"], prediction["predicted_raw"]
    )
    messages = [{"role": "user", "content": prompt}]
    inputs = judge_tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(judge_model.device)

    with torch.no_grad():
        output_ids = judge_model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=judge_tokenizer.eos_token_id,
        )
    prompt_len = inputs["input_ids"].shape[1]
    generated_text = judge_tokenizer.decode(
        output_ids[0][prompt_len:], skip_special_tokens=True
    ).strip()

    parsed = try_parse_json(generated_text)
    if parsed is None or parsed.get("failure_type") not in FAILURE_TAXONOMY:
        return {"failure_type": "unparseable_judge_output", "reasoning": generated_text[:200]}
    return parsed


def diagnose_failures(predictions, judge_model, judge_tokenizer, sample_size=200, seed=42):
    """Diagnose why predictions failed exact-match, on a capped random sample
    so a badly-failing candidate (e.g. QLoRA at ~69% failure) doesn't blow up
    judge runtime the way running it on every failure would.
    """
    failures = [p for p in predictions if p["predicted_parsed"] != p["expected"]]
    if len(failures) > sample_size:
        failures = random.Random(seed).sample(failures, sample_size)

    diagnoses = []
    counts = {ft: 0 for ft in FAILURE_TAXONOMY + ["unparseable_judge_output"]}
    for prediction in failures:
        diagnosis = diagnose_prediction(judge_model, judge_tokenizer, prediction)
        diagnoses.append({**prediction, **diagnosis})
        counts[diagnosis["failure_type"]] += 1

    return diagnoses, counts


def log_diagnosis_summary(task, prefix, counts, n_failures_total):
    """Log the failure-type breakdown as a ClearML table. Diagnostic only —
    does not feed into the quality gate.
    """
    logger = task.get_logger()
    sampled_n = sum(counts.values())
    rows = [[failure_type, count] for failure_type, count in counts.items() if count > 0]
    logger.report_table(
        title="judge_failure_diagnosis",
        series=prefix,
        iteration=0,
        table_plot=[["failure_type", "count"], *rows],
    )
    print(
        f"[{prefix}] judge diagnosed {sampled_n}/{n_failures_total} failures: "
        f"{ {ft: c for ft, c in counts.items() if c > 0} }"
    )
