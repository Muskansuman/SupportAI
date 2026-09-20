"""Print the real unique intent/category/urgency values in the processed
dataset, so data/kb/articles.jsonl can be written to actually match the
data instead of guessed intent names.

Run: python3 -m src.rag.list_intents
"""
import json
from collections import Counter

from src.config import DATA_PROCESSED_DIR


def load_all_outputs():
    outputs = []
    for split in ("train", "val", "test"):
        path = DATA_PROCESSED_DIR / f"{split}.jsonl"
        with open(path) as f:
            outputs.extend(json.loads(line)["output"] for line in f)
    return outputs


def main():
    outputs = load_all_outputs()
    intents = Counter(o["intent"] for o in outputs)
    categories = Counter(o["category"] for o in outputs)
    urgencies = Counter(o["urgency"] for o in outputs)

    print(f"{len(intents)} unique intents:")
    for intent, count in intents.most_common():
        print(f"  {intent}: {count}")

    print(f"\n{len(categories)} unique categories:")
    for category, count in categories.most_common():
        print(f"  {category}: {count}")

    print(f"\n{len(urgencies)} unique urgency levels:")
    for urgency, count in urgencies.most_common():
        print(f"  {urgency}: {count}")


if __name__ == "__main__":
    main()
