"""Fine-tune Qwen2.5-0.5B (LoRA) to classify support messages into the demo's
12 intents + urgency, evaluate it on held-out conversations, and register the
adapter in ClearML.

    python scripts/train_support_classifier.py            # train + evaluate + register
    python scripts/train_support_classifier.py --no-clearml

Differences from the earlier ticket-extractor training that matter:
  * EOS is appended to every target and kept in the loss. (The old trainer
    padded with EOS and masked every pad position, so the model never learned
    to stop after its JSON.)
  * Prompt and response are tokenized separately, exactly as at inference.
  * 128-token context: the messages are short, so this is ~4x lighter than 512.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq, Trainer, TrainingArguments

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import MODEL_NAME, OUTPUTS_DIR, SUPPORT_MODEL_REGISTRY_NAME  # noqa: E402
from src.prompting import build_prompt  # noqa: E402
from src.support.classifier import INSTRUCTION, SupportClassifier, format_target  # noqa: E402

DATA = ROOT / "data" / "synthetic" / "support_conversations.json"
OUTPUT_DIR = OUTPUTS_DIR / "support-classifier"
MAX_LENGTH = 128
LORA_R, LORA_ALPHA, LORA_DROPOUT = 16, 32, 0.05
LEARNING_RATE = 2e-4
EPOCHS = 3
BATCH_SIZE = 8
GRAD_ACCUM = 2  # effective batch 16; small micro-batches because the 152k-token vocab makes logits large

# Promotion gate: measured on held-out data, never on the training split.
GATE = {"test_intent_accuracy": 0.90, "test_unseen_intent_accuracy": 0.75, "valid_json_rate": 0.98}


class ConversationDataset(Dataset):
    def __init__(self, rows, tokenizer):
        self.items = []
        eos = tokenizer.eos_token_id
        for row in rows:
            prompt_ids = tokenizer(build_prompt(INSTRUCTION, row["text"]), truncation=True, max_length=MAX_LENGTH - 24)["input_ids"]
            response_ids = tokenizer(format_target(row["intent"], row["urgency"]), add_special_tokens=False)["input_ids"] + [eos]
            self.items.append({"input_ids": prompt_ids + response_ids, "labels": [-100] * len(prompt_ids) + response_ids})

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.items[i]


def expected_calibration_error(confidences, correct, bins=10):
    total, ece = len(confidences), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if idx:
            ece += len(idx) / total * abs(sum(correct[i] for i in idx) / len(idx) - sum(confidences[i] for i in idx) / len(idx))
    return ece


def evaluate_split(classifier, rows, name):
    predictions = []
    for row in rows:
        out = classifier.classify(row["text"])
        predictions.append({"conversation_id": row["conversation_id"], "text": row["text"], "gold_intent": row["intent"], "gold_urgency": row["urgency"], "ambiguous": row["ambiguous"], **out})
    valid = [p for p in predictions if p["intent"] is not None]
    intent_ok = [p["intent"] == p["gold_intent"] for p in predictions]
    urgency_ok = [p["urgency"] == p["gold_urgency"] for p in predictions]
    clear = [p for p in predictions if not p["ambiguous"]]
    metrics = {
        "n": len(predictions),
        "valid_json_rate": len(valid) / len(predictions),
        "intent_accuracy": sum(intent_ok) / len(predictions),
        "intent_accuracy_unambiguous": sum(p["intent"] == p["gold_intent"] for p in clear) / max(len(clear), 1),
        "urgency_accuracy": sum(urgency_ok) / len(predictions),
        "mean_confidence": sum(p["confidence"] for p in predictions) / len(predictions),
        "ece": expected_calibration_error([p["confidence"] for p in predictions], [float(ok) for ok in intent_ok]),
    }
    print(f"[{name}] " + "  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items()), flush=True)
    return metrics, predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-clearml", action="store_true")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    args = parser.parse_args()

    rows = json.loads(DATA.read_text())
    split = {name: [r for r in rows if r["split"] == name] for name in ("train", "val", "test", "test_unseen")}
    print({k: len(v) for k, v in split.items()}, flush=True)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    task = None
    if not args.no_clearml:
        from src.clearml_utils import start_task

        task = start_task("supportai-fashion-classifier-lora", config={"model_name": MODEL_NAME, "lora_r": LORA_R, "epochs": args.epochs, "learning_rate": LEARNING_RATE, "train_examples": len(split["train"])})

    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], bias="none", task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(OUTPUT_DIR / "checkpoints"),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            per_device_eval_batch_size=8,
            num_train_epochs=args.epochs,
            learning_rate=LEARNING_RATE,
            warmup_steps=0.03,
            logging_steps=20,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            bf16=True,
            report_to="none",
            remove_unused_columns=False,
        ),
        train_dataset=ConversationDataset(split["train"], tokenizer),
        eval_dataset=ConversationDataset(split["val"], tokenizer),
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8),
    )
    started = time.time()
    trainer.train()
    print(f"training took {time.time() - started:.0f}s", flush=True)

    adapter_dir = OUTPUT_DIR / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    model.eval()
    model.config.use_cache = True
    classifier = SupportClassifier(model, tokenizer)
    all_metrics = {}
    for name in ("test", "test_unseen"):
        metrics, predictions = evaluate_split(classifier, split[name], name)
        all_metrics[name] = metrics
        with open(OUTPUT_DIR / f"predictions_{name}.jsonl", "w") as f:
            f.writelines(json.dumps(p) + "\n" for p in predictions)
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(all_metrics, indent=2))

    gate_values = {
        "test_intent_accuracy": all_metrics["test"]["intent_accuracy"],
        "test_unseen_intent_accuracy": all_metrics["test_unseen"]["intent_accuracy"],
        "valid_json_rate": min(all_metrics["test"]["valid_json_rate"], all_metrics["test_unseen"]["valid_json_rate"]),
    }
    passed = all(gate_values[k] >= GATE[k] for k in GATE)
    print("gate:", {k: (round(gate_values[k], 4), GATE[k]) for k in GATE}, "->", "PASS" if passed else "FAIL", flush=True)

    if task is not None:
        from clearml import Model, OutputModel

        logger = task.get_logger()
        for split_name, metrics in all_metrics.items():
            for key, value in metrics.items():
                logger.report_scalar(title=f"eval_{split_name}", series=key, value=float(value), iteration=0)
        output_model = OutputModel(task=task, name=SUPPORT_MODEL_REGISTRY_NAME, framework="PyTorch")
        output_model.update_weights(str(adapter_dir), async_enable=False)
        output_model.tags = ["candidate"]
        if passed:
            from src.config import CLEARML_PROJECT_NAME

            for old in Model.query_models(project_name=CLEARML_PROJECT_NAME, model_name=SUPPORT_MODEL_REGISTRY_NAME, tags=["production"]):
                old.tags = [t for t in old.tags if t != "production"] + ["archived"]
            output_model.tags = ["production"]
            print("registered and promoted:", output_model.id, flush=True)
        else:
            output_model.tags = ["rejected"]
            print("registered but NOT promoted (gate failed):", output_model.id, flush=True)
        task.close()


if __name__ == "__main__":
    main()
