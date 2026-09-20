"""Evaluate the support system on held-out synthetic conversations.

    python scripts/evaluate_support.py                 # reuse predictions saved by training
    python scripts/evaluate_support.py --recompute     # run the classifier again

Measures, per split: intent (accuracy, per-class precision/recall/F1,
confusion matrix), urgency, the escalation decision, the 3-way decision, how
well confidence tracks correctness, and regex entity extraction. The
escalation/decision numbers run the real rule engine on the classifier's
PREDICTED intent and confidence, so classifier mistakes propagate the way they
would in production.

Splits: `test` shares phrasing templates with training; `test_unseen` uses
phrasings held out of training entirely. Both are synthetic and templated, so
treat the numbers as a check that the pipeline works, not as real-world
accuracy. Results are written to evaluation/results.json.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.support import config  # noqa: E402
from src.support.context import resolve_order  # noqa: E402
from src.support.decision import decide  # noqa: E402
from src.support.eligibility import evaluate_all  # noqa: E402
from src.support.entities import extract_entities  # noqa: E402
from src.support.store import DataStore  # noqa: E402

PREDICTIONS_DIR = ROOT / "outputs" / "support-classifier"
RESULTS = ROOT / "evaluation" / "results.json"
DECISIONS = ["AUTO_RESOLVE", "CLARIFICATION_REQUIRED", "HUMAN_ESCALATION"]


def prf(gold, pred, labels):
    p, r, f, s = precision_recall_fscore_support(gold, pred, labels=labels, zero_division=0)
    per_class = {label: {"precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4), "f1": round(float(f[i]), 4), "support": int(s[i])} for i, label in enumerate(labels)}
    present = [i for i in range(len(labels)) if s[i] > 0]
    macro = float(sum(f[i] for i in present) / len(present))
    weighted = float(sum(f[i] * s[i] for i in present) / sum(s[i] for i in present))
    return per_class, round(macro, 4), round(weighted, 4)


def confusion(gold, pred, labels):
    return {"labels": labels, "matrix": confusion_matrix(gold, pred, labels=labels).tolist()}


def accuracy(gold, pred):
    return round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 4)


def calibration(confidences, correct):
    """Reliability by band + expected calibration error."""
    bands = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for c, ok in zip(confidences, correct):
        bands[config.confidence_band(c)].append(ok)
    by_band = {b: {"n": len(v), "accuracy": round(sum(v) / len(v), 4) if v else None} for b, v in bands.items()}
    ece = 0.0
    for b in range(10):
        idx = [i for i, c in enumerate(confidences) if b / 10 <= c < (b + 1) / 10 or (b == 9 and c == 1.0)]
        if idx:
            ece += len(idx) / len(confidences) * abs(sum(correct[i] for i in idx) / len(idx) - sum(confidences[i] for i in idx) / len(idx))
    return {"by_band": by_band, "ece": round(ece, 4), "mean_confidence": round(sum(confidences) / len(confidences), 4)}


def load_predictions(split, rows, recompute):
    path = PREDICTIONS_DIR / f"predictions_{split}.jsonl"
    if path.exists() and not recompute:
        return {p["conversation_id"]: p for p in map(json.loads, path.read_text().splitlines())}
    from src.support.service import load_classifier

    classifier, _ = load_classifier()
    return {r["conversation_id"]: {**classifier.classify(r["text"]), "conversation_id": r["conversation_id"]} for r in rows}


def predicted_decision(store, row, pred):
    intent = pred["intent"] or "GENERAL_QUERY"
    confidence = pred["confidence"] if pred["intent"] else 0.0
    entities = extract_entities(row["text"])
    customer_orders = store.customer_orders(row["customer_id"])
    candidates = []
    if entities.get("order_id"):
        order = store.get_order(entities["order_id"])
        if order is not None and order["customer_id"] != row["customer_id"]:
            order = None
    else:
        order, candidates = resolve_order(intent, row["text"], customer_orders, store.products)
    evaluation = evaluate_all(order, store.get_product(order["product_id"]), entities.get("requested_size")) if order else None
    return decide(intent=intent, confidence=confidence, text=row["text"], order=order, evaluation=evaluation, requested_size=entities.get("requested_size"), order_id_not_found=entities.get("order_id") if entities.get("order_id") and not order else None, candidate_orders=candidates)


def evaluate_split(store, name, rows, predictions):
    gold_intent = [r["intent"] for r in rows]
    pred_intent = [predictions[r["conversation_id"]]["intent"] or "INVALID" for r in rows]
    gold_urgency = [r["urgency"] for r in rows]
    pred_urgency = [predictions[r["conversation_id"]]["urgency"] or "INVALID" for r in rows]
    confidences = [predictions[r["conversation_id"]]["confidence"] for r in rows]
    correct = [float(g == p) for g, p in zip(gold_intent, pred_intent)]

    labels = list(config.INTENTS)
    per_class, macro, weighted = prf(gold_intent, pred_intent, labels)
    u_per_class, u_macro, _ = prf(gold_urgency, pred_urgency, list(config.URGENCY_LEVELS))

    decisions = [predicted_decision(store, r, predictions[r["conversation_id"]]) for r in rows]
    pred_action = [d["action"] for d in decisions]
    gold_action = [r["expected_decision"] for r in rows]
    gold_esc = ["ESCALATE" if r["escalation_needed"] else "NO" for r in rows]
    pred_esc = ["ESCALATE" if d["action"] == "HUMAN_ESCALATION" else "NO" for d in decisions]
    esc_pc, _, _ = prf(gold_esc, pred_esc, ["ESCALATE", "NO"])

    clear = [i for i, r in enumerate(rows) if not r["ambiguous"]]
    ambiguous = [i for i, r in enumerate(rows) if r["ambiguous"]]
    with_id = [r for r in rows if r["order_id"]]
    with_size = [r for r in rows if r["requested_size"]]

    result = {
        "n": len(rows),
        "intent": {
            "accuracy": accuracy(gold_intent, pred_intent),
            "accuracy_unambiguous": accuracy([gold_intent[i] for i in clear], [pred_intent[i] for i in clear]),
            "ambiguous_n": len(ambiguous),
            "macro_f1": macro,
            "weighted_f1": weighted,
            "per_class": per_class,
            "confusion": confusion(gold_intent, pred_intent, labels + (["INVALID"] if "INVALID" in pred_intent else [])),
        },
        "urgency": {"accuracy": accuracy(gold_urgency, pred_urgency), "macro_f1": u_macro, "per_class": u_per_class, "confusion": confusion(gold_urgency, pred_urgency, list(config.URGENCY_LEVELS))},
        "escalation": {"accuracy": accuracy(gold_esc, pred_esc), **{k: esc_pc["ESCALATE"][k] for k in ("precision", "recall", "f1")}, "gold_positive": sum(g == "ESCALATE" for g in gold_esc), "confusion": confusion(gold_esc, pred_esc, ["ESCALATE", "NO"])},
        "decision": {
            "accuracy": accuracy(gold_action, pred_action),
            # Automated when a question or a person was needed: the costly direction.
            "unsafe_auto_resolve_rate": round(sum(g != "AUTO_RESOLVE" and p == "AUTO_RESOLVE" for g, p in zip(gold_action, pred_action)) / len(rows), 4),
            # Asked or escalated when it could have resolved: safe but less helpful.
            "over_cautious_rate": round(sum(g == "AUTO_RESOLVE" and p != "AUTO_RESOLVE" for g, p in zip(gold_action, pred_action)) / len(rows), 4),
            "confusion": confusion(gold_action, pred_action, DECISIONS),
        },
        "confidence": calibration(confidences, correct),
        "entities": {
            "order_id_recall": round(sum(extract_entities(r["text"]).get("order_id") == r["order_id"] for r in with_id) / max(len(with_id), 1), 4),
            "size_recall": round(sum(extract_entities(r["text"]).get("requested_size") == r["requested_size"] for r in with_size) / max(len(with_size), 1), 4),
        },
    }
    i, e, d = result["intent"], result["escalation"], result["decision"]
    print(f"[{name}] n={len(rows)} intent acc={i['accuracy']:.3f} (unambiguous {i['accuracy_unambiguous']:.3f}) macroF1={i['macro_f1']:.3f} | urgency acc={result['urgency']['accuracy']:.3f} | escalation P={e['precision']:.3f} R={e['recall']:.3f} F1={e['f1']:.3f} | decision acc={d['accuracy']:.3f} unsafe-auto={d['unsafe_auto_resolve_rate']:.3f} over-cautious={d['over_cautious_rate']:.3f} | ECE={result['confidence']['ece']:.3f}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()

    store = DataStore()
    rows = store.conversations()
    results = {}
    for split in ("test", "test_unseen"):
        split_rows = [r for r in rows if r["split"] == split]
        results[split] = evaluate_split(store, split, split_rows, load_predictions(split, split_rows, args.recompute))

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"seed": store.meta["seed"], "counts": store.meta["counts"]},
        "splits": results,
        "notes": [
            "Measured on synthetic, template-generated conversations, so these numbers show the pipeline works end to end; they are not real-world accuracy.",
            "test shares phrasing templates with the training data. test_unseen uses phrasings that were never in training, and is the more honest generalisation check.",
            "Ambiguous messages are labelled with a random plausible intent, so intent accuracy on them is low by design; the aim there is low confidence, not a right answer.",
            "Confidence is the model's token probability for the predicted intent. It is not a calibrated probability; the ECE and per-band accuracy show how well it tracks correctness.",
            "Escalation and decision metrics run the real rule engine on the classifier's predicted intent and confidence.",
        ],
    }
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(output, indent=1))
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
