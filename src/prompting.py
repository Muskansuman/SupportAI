"""Prompt formatting, tokenization with label masking, generation, and
JSON-parsing helpers shared across training, evaluation, and serving.
"""
import json
import re

import torch

RESPONSE_MARKER = "### Response:\n"


def build_prompt(instruction, input_text):
    return f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n{RESPONSE_MARKER}"


def format_example(example):
    """Turn a raw {instruction, input, output} row into one training text field."""
    prompt = build_prompt(example["instruction"], example["input"])
    response = json.dumps(example["output"])
    example["text"] = prompt + response
    return example


def make_tokenize_fn(tokenizer, max_length=512):
    """Return a tokenize_fn that masks the prompt (and padding) out of the
    loss, so only the JSON response contributes to training loss.
    """
    def tokenize_fn(example):
        full_text = example["text"]
        split_idx = full_text.index(RESPONSE_MARKER) + len(RESPONSE_MARKER)
        prompt_part = full_text[:split_idx]

        tokens = tokenizer(full_text, truncation=True, max_length=max_length, padding="max_length")
        prompt_ids = tokenizer(prompt_part, truncation=True, max_length=max_length)["input_ids"]

        labels = tokens["input_ids"].copy()
        for i in range(min(len(prompt_ids), len(labels))):
            labels[i] = -100
        labels = [l if l != tokenizer.pad_token_id else -100 for l in labels]

        tokens["labels"] = labels
        return tokens

    return tokenize_fn


def generate_prediction(model, tokenizer, instruction, input_text, max_new_tokens=40):
    prompt = build_prompt(instruction, input_text)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return generated_text[len(prompt):].strip()


def try_parse_json(text):
    """Parse near-JSON model output; models often produce minor formatting issues."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Non-greedy: stop at the first closing brace. Our schema is always a flat,
    # single-level object, so a well-formed response has exactly one `{...}`
    # anyway — this only changes behavior when the model rambles past a
    # correct answer (e.g. repeating a shrinking echo of the same object),
    # where a greedy match would span all the repeats into one invalid blob
    # instead of recovering the first, correct object.
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None
