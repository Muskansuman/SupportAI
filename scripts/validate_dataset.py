"""Check the generated dataset for internal consistency and print its shape.

    python scripts/validate_dataset.py [--check-determinism]

Exits non-zero if any rule fails. The distribution tables are printed so it's
visible that the labels aren't degenerate (e.g. everything AUTO_RESOLVE).
"""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.support import config  # noqa: E402
from src.support.context import resolve_order  # noqa: E402
from src.support.eligibility import evaluate_cancellation, evaluate_exchange, evaluate_return, parse_ts, replacement_sizes  # noqa: E402
from src.support.entities import extract_entities  # noqa: E402
from src.support.urgency import text_urgency  # noqa: E402

DATA = ROOT / "data" / "synthetic"
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def data_hash():
    h = hashlib.sha256()
    for path in sorted(DATA.rglob("*")):
        if path.is_file():
            h.update(path.name.encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def main():
    products, customers, orders, convs = load("products"), load("customers"), load("orders"), load("support_conversations")
    meta = json.loads((DATA / "meta.json").read_text())
    now = config.DEMO_NOW
    P = {p["product_id"]: p for p in products}
    C = {c["customer_id"]: c for c in customers}
    O = {o["order_id"]: o for o in orders}

    check((len(products), len(customers), len(orders), len(convs)) == (1000, 2000, 10000, 5000), "dataset sizes are not 1000/2000/10000/5000")
    check(len(list((DATA / "knowledge_base").glob("*.md"))) == 10, "expected 10 knowledge-base documents")
    check(len(P) == 1000 and len(C) == 2000 and len(O) == 10000, "duplicate ids found")

    by_customer = {}
    for o in orders:
        by_customer.setdefault(o["customer_id"], []).append(o)

    for o in orders:
        oid = o["order_id"]
        check(o["customer_id"] in C, f"{oid}: unknown customer")
        p = P.get(o["product_id"])
        check(p is not None, f"{oid}: unknown product")
        if p is None:
            continue
        check((o["product_name"], o["brand"], o["category"], o["color"], o["price"], o["mrp"]) == (p["name"], p["brand"], p["category"], p["color"], p["price"], p["mrp"]), f"{oid}: does not match the product catalog")
        check(o["size"] in p["sizes"], f"{oid}: size not offered for the product")
        check(all(s in p["sizes"] and s != o["size"] and p["stock_by_size"][s] > 0 for s in o["replacement_sizes"]), f"{oid}: bad replacement sizes")
        check(o["replacement_sizes"] == replacement_sizes(o, p), f"{oid}: replacement sizes differ from stock")

        placed = parse_ts(o["order_date"])
        check(placed <= now, f"{oid}: order in the future")
        for field in ("delivery_date", "cancelled_date", "return_initiated_date", "refund_initiated_date"):
            if o[field]:
                ts = parse_ts(o[field])
                check(ts > placed, f"{oid}: {field} is not after the order date")
                check(ts <= now or field == "expected_delivery_date", f"{oid}: {field} is in the future")
        if o["delivery_date"] and o["return_initiated_date"]:
            check(parse_ts(o["return_initiated_date"]) > parse_ts(o["delivery_date"]), f"{oid}: return before delivery")
        if o["expected_delivery_date"]:
            check(parse_ts(o["expected_delivery_date"]) > placed, f"{oid}: expected delivery before order")

        status = o["status"]
        check((status in ("delivered", "returned", "return_initiated", "exchange_initiated")) == bool(o["delivery_date"]), f"{oid}: delivery_date inconsistent with status {status}")
        check((status == "cancelled") == bool(o["cancelled_date"]), f"{oid}: cancelled_date inconsistent with status")
        check(all(parse_ts(e["timestamp"]) <= now for e in o["tracking_events"]), f"{oid}: tracking event in the future")

        check(o["return_eligible"] == evaluate_return(o, p)["eligible"], f"{oid}: return_eligible flag differs from the rules")
        check(o["exchange_eligible"] == evaluate_exchange(o, p)["eligible"], f"{oid}: exchange_eligible flag differs from the rules")
        check(o["cancellable"] == evaluate_cancellation(o)["eligible"], f"{oid}: cancellable flag differs from the rules")
        if o["exchange_eligible"]:
            check(bool(o["replacement_sizes"]), f"{oid}: exchange eligible but no replacement size")

    split_texts = {}
    entity_hits = size_hits = with_id = with_size = 0
    for cv in convs:
        cid = cv["conversation_id"]
        check(cv["intent"] in config.INTENTS, f"{cid}: bad intent")
        check(cv["urgency"] in config.URGENCY_LEVELS, f"{cid}: bad urgency")
        check(cv["customer_id"] in C, f"{cid}: unknown customer")
        if cv["order_id"]:
            with_id += 1
            o = O.get(cv["order_id"])
            check(o is not None, f"{cid}: unknown order {cv['order_id']}")
            if o:
                check(o["customer_id"] == cv["customer_id"], f"{cid}: order belongs to another customer")
            check(cv["order_id"].lower() in cv["text"].lower(), f"{cid}: order id not in the text")
            entity_hits += extract_entities(cv["text"]).get("order_id") == cv["order_id"]
        check(cv["escalation_needed"] == (cv["expected_decision"] == "HUMAN_ESCALATION"), f"{cid}: escalation label inconsistent")
        if not cv["ambiguous"]:
            check(cv["urgency"] == text_urgency(cv["intent"], cv["text"]), f"{cid}: urgency label differs from the rule")
        if cv["requested_size"]:
            with_size += 1
            size_hits += extract_entities(cv["text"]).get("requested_size") == cv["requested_size"]
        check((cv["split"] == "test_unseen") == (cv["template_group"] == "unseen"), f"{cid}: split/template group mismatch")
        split_texts.setdefault(cv["split"], set()).add(cv["text"].lower())

    check(len({cv["text"].lower() for cv in convs}) == len(convs), "duplicate conversation texts")
    check(not (split_texts["train"] & split_texts["test"]), "train/test text overlap")
    check(not (split_texts["train"] & split_texts["test_unseen"]), "train/test_unseen text overlap")

    # ---- showcase order used in the acceptance tests
    demo_id = meta["demo_customer_id"]
    o = O["MYN-DEMO-004281"]
    p = P[o["product_id"]]
    check(o["customer_id"] == demo_id and o["status"] == "delivered" and o["size"] == "M" and o["price"] == 999, "showcase order 004281 has the wrong shape")
    check(o["exchange_eligible"] and o["return_eligible"] and o["replacement_sizes"] == ["S", "L", "XL"], "showcase order 004281 should allow exchange to S/L/XL")
    check(p["name"] == "Urbanloom Men Solid Black T-Shirt", "showcase product name")
    demo_orders = by_customer[demo_id]
    for intent, expected in [("RETURN_REQUEST", "MYN-DEMO-004281"), ("EXCHANGE_REQUEST", "MYN-DEMO-004281"), ("DAMAGED_PRODUCT", "MYN-DEMO-004281"), ("DELIVERY_ISSUE", "MYN-DEMO-007312"), ("PAYMENT_ISSUE", "MYN-DEMO-002210"), ("CANCEL_ORDER", "MYN-DEMO-009001")]:
        found, _ = resolve_order(intent, "my order", demo_orders, P)
        check(found is not None and found["order_id"] == expected, f"demo customer: {intent} should resolve to {expected}, got {found and found['order_id']}")
    _, refund_candidates = resolve_order("REFUND_REQUEST", "my order", demo_orders, P)
    check(len(refund_candidates) >= 2, "demo customer: refund should be ambiguous between orders")

    # ---- report
    def table(title, counter):
        total = sum(counter.values())
        print(f"\n{title}")
        for key, n in counter.most_common():
            print(f"  {str(key):28s} {n:6d}  {n / total:6.1%}")

    table("order status", Counter(o["status"] for o in orders))
    table("payment status", Counter(o["payment_status"] for o in orders))
    table("conversation intent", Counter(c["intent"] for c in convs))
    table("conversation urgency", Counter(c["urgency"] for c in convs))
    table("expected decision", Counter(c["expected_decision"] for c in convs))
    table("expected outcome", Counter(c["expected_outcome"] for c in convs))
    table("split", Counter(c["split"] for c in convs))
    print(f"\nreturn eligible orders: {sum(o['return_eligible'] for o in orders)}   exchange eligible: {sum(o['exchange_eligible'] for o in orders)}   cancellable: {sum(o['cancellable'] for o in orders)}")
    print(f"conversations mentioning an order id: {with_id}   regex order-id extraction: {entity_hits / max(with_id, 1):.1%}")
    print(f"conversations with a requested size: {with_size}   regex size extraction: {size_hits / max(with_size, 1):.1%}")

    if "--check-determinism" in sys.argv:
        before = data_hash()
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_dataset.py")], check=True, capture_output=True)
        check(before == data_hash(), "regenerating changed the dataset (not deterministic)")
        print("\ndeterminism: regenerated dataset is byte-identical" if before == data_hash() else "")

    if failures:
        print(f"\n{len(failures)} FAILURES (showing 25):")
        for f in failures[:25]:
            print("  -", f)
        sys.exit(1)
    print("\nAll consistency checks passed.")


if __name__ == "__main__":
    main()
