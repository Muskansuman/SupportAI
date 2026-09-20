"""Intent + urgency classifier: the fine-tuned Qwen adapter, plus confidence.

Confidence is the model's own probability of the label it produced: the
product of the probabilities of the tokens that make up the intent value
(greedy decoding). It is a real number derived from the model, not a display
value, but it is NOT a calibrated probability: a model can be confidently
wrong. The evaluation script reports how well it tracks accuracy.
"""
import json
import threading

import torch

from src.prompting import build_prompt, try_parse_json
from src.support import config

INSTRUCTION = "Classify this support message."


def _value_token_probs(tokenizer, generated_ids, step_probs, key):
    """Probability mass of the tokens that spell the value of `"key": "<value>"`."""
    pieces, text = [], ""
    for token_id in generated_ids:
        piece = tokenizer.decode([token_id])
        pieces.append((len(text), len(text) + len(piece)))
        text += piece

    marker = f'"{key}": "'
    start = text.find(marker)
    if start < 0:
        return None, None
    value_start = start + len(marker)
    value_end = text.find('"', value_start)
    if value_end < 0:
        return None, None

    prob = 1.0
    for (lo, hi), p in zip(pieces, step_probs):
        if hi > value_start and lo < value_end:
            prob *= p
    return text[value_start:value_end], prob


class SupportClassifier:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self._lock = threading.Lock()

    def classify(self, text, max_new_tokens=40):
        with self._lock:
            return self._classify(text, max_new_tokens)

    @torch.no_grad()
    def _classify(self, text, max_new_tokens):
        prompt = build_prompt(INSTRUCTION, text)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        output = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            output_scores=True,
            return_dict_in_generate=True,
            stop_strings=["}"],
            tokenizer=self.tokenizer,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        generated = output.sequences[0][inputs["input_ids"].shape[1]:].tolist()
        step_probs = [torch.softmax(score[0].float(), dim=-1)[token].item() for score, token in zip(output.scores, generated)]

        raw = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        parsed = try_parse_json(raw) or {}

        intent, intent_conf = _value_token_probs(self.tokenizer, generated, step_probs, "intent")
        urgency, urgency_conf = _value_token_probs(self.tokenizer, generated, step_probs, "urgency")

        intent = parsed.get("intent", intent)
        urgency = parsed.get("urgency", urgency)
        valid_intent = intent in config.INTENTS
        valid_urgency = urgency in config.URGENCY_LEVELS

        return {
            "intent": intent if valid_intent else None,
            "urgency": urgency if valid_urgency else None,
            # An unparseable or out-of-vocabulary label gets zero confidence,
            # which routes the request to clarification/handoff.
            "confidence": float(intent_conf) if valid_intent and intent_conf is not None else 0.0,
            "urgency_confidence": float(urgency_conf) if valid_urgency and urgency_conf is not None else 0.0,
            "raw": raw,
        }


def format_target(intent, urgency):
    return json.dumps({"intent": intent, "urgency": urgency})
