"""Fetch, validate, and split the support-ticket training data.

Covers what were cells 3b/4/5 of the original notebook: pull raw tickets
(from the Bitext customer-support dataset), drop malformed/duplicate rows,
then split into train/val/test JSONL files under data/processed/.
"""
import json

import pandas as pd
from datasets import load_dataset

from src.config import DATA_PROCESSED_DIR, RAW_TICKETS_PATH

# Real customer-support utterances, 27 intents across 11 categories,
# ~1000 rows/intent. https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset
# Its own "instruction" column is actually the customer's message and its
# "category"/"intent" columns already match what we need — only "urgency"
# has no equivalent upstream and has to be assigned ourselves.
BITEXT_DATASET_NAME = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"

# Bitext has no urgency label, so this assigns one per intent by hand:
# HIGH = money-impacting or already-escalated; MEDIUM = time-sensitive but
# not urgent; LOW = informational/self-serve. Adjust freely — this is a
# judgment call, not something derived from the data.
INTENT_TO_URGENCY = {
    "complaint": "high",
    "payment_issue": "high",
    "contact_human_agent": "high",
    "delete_account": "high",
    "cancel_order": "high",
    "change_order": "medium",
    "change_shipping_address": "medium",
    "track_order": "medium",
    "track_refund": "medium",
    "get_refund": "medium",
    "registration_problems": "medium",
    "recover_password": "medium",
    "switch_account": "medium",
    "contact_customer_service": "medium",
    "edit_account": "medium",
    "create_account": "low",
    "check_invoice": "low",
    "get_invoice": "low",
    "check_payment_methods": "low",
    "check_refund_policy": "low",
    "check_cancellation_fee": "low",
    "delivery_options": "low",
    "delivery_period": "low",
    "newsletter_subscription": "low",
    "review": "low",
    "place_order": "low",
    "set_up_shipping_address": "low",
}

REQUIRED_FIELDS = {"instruction", "input", "output"}
EXPECTED_OUTPUT_KEYS = {"intent", "urgency", "category"}


def fetch_raw_tickets(out_path=RAW_TICKETS_PATH):
    """Pull the Bitext dataset and reshape it into our {instruction, input,
    output} row format, writing the result as JSONL."""
    bitext = load_dataset(BITEXT_DATASET_NAME, split="train")

    rows = []
    for row in bitext:
        intent = row["intent"]
        rows.append({
            "instruction": "Classify this support ticket.",
            "input": row["instruction"].strip(),
            "output": {
                "intent": intent,
                "urgency": INTENT_TO_URGENCY[intent],
                "category": row["category"].lower(),
            },
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"Fetched {len(rows)} Bitext support ticket examples -> {out_path}")
    return rows


def _is_valid_output(o):
    return isinstance(o, dict) and EXPECTED_OUTPUT_KEYS.issubset(o.keys())


def validate_raw_tickets(raw_path=RAW_TICKETS_PATH):
    """Load raw JSONL, drop malformed/empty/duplicate rows, return the clean DataFrame."""
    records = [json.loads(line) for line in open(raw_path)]
    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} raw records")

    missing_field_rows = df[~df.apply(lambda r: REQUIRED_FIELDS.issubset(r.index), axis=1)]
    empty_rows = df[(df["input"].str.strip() == "") | (df["output"].isna())]
    duplicate_rows = df[df.duplicated(subset=["input"], keep=False)]
    invalid_output_rows = df[~df["output"].apply(_is_valid_output)]

    print(f"Rows missing required fields: {len(missing_field_rows)}")
    print(f"Rows with empty input/output: {len(empty_rows)}")
    print(f"Duplicate input rows: {len(duplicate_rows)}")
    print(f"Rows with invalid output schema: {len(invalid_output_rows)}")

    bad_indices = (
        set(missing_field_rows.index)
        | set(empty_rows.index)
        | set(duplicate_rows.index)
        | set(invalid_output_rows.index)
    )
    clean_df = df.drop(index=bad_indices).reset_index(drop=True)
    print(f"Clean dataset: {len(clean_df)} rows (dropped {len(bad_indices)})")
    return clean_df


def _save_jsonl(df, path):
    with open(path, "w") as f:
        for _, row in df.iterrows():
            f.write(json.dumps(row.to_dict()) + "\n")


def split_dataset(clean_df, seed=42, out_dir=DATA_PROCESSED_DIR):
    """Shuffle and split into 80/10/10 train/val/test JSONL files."""
    clean_df = clean_df.sample(frac=1, random_state=seed).reset_index(drop=True)

    n = len(clean_df)
    train_end = int(n * 0.8)
    val_end = train_end + int(n * 0.1)

    train_df = clean_df.iloc[:train_end]
    val_df = clean_df.iloc[train_end:val_end]
    test_df = clean_df.iloc[val_end:]
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    _save_jsonl(train_df, out_dir / "train.jsonl")
    _save_jsonl(val_df, out_dir / "val.jsonl")
    _save_jsonl(test_df, out_dir / "test.jsonl")
    print(f"Splits saved to {out_dir}/")

    return train_df, val_df, test_df


def build_dataset():
    """Run the full fetch -> validate -> split pipeline."""
    fetch_raw_tickets()
    clean_df = validate_raw_tickets()
    return split_dataset(clean_df)


if __name__ == "__main__":
    build_dataset()
