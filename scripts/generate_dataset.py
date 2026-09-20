"""Generate the synthetic fashion e-commerce dataset used by the support demo.

    python scripts/generate_dataset.py

Writes to data/synthetic/: products, customers, orders and
support_conversations (JSON + CSV), knowledge_base/*.md and meta.json.
A fixed seed makes every run identical. All names, brands and contact details
are fictional; nothing here comes from a real store or real people.

Labels are computed with the same code the live pipeline runs
(src/support/*), so the data and the runtime cannot disagree.
"""
import csv
import json
import random
import re
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.conversation_templates import (  # noqa: E402
    AMBIGUOUS,
    AMBIGUOUS_LABELS,
    INTENT_WEIGHTS,
    PREFIXES,
    SENSITIVE_SUFFIXES,
    SUFFIXES,
    TEMPLATES,
    UNSEEN_PER_LIST,
)
from scripts.kb_documents import KB_DOCUMENTS  # noqa: E402
from src.support import config  # noqa: E402
from src.support.context import candidate_orders, resolve_order  # noqa: E402
from src.support.decision import decide  # noqa: E402
from src.support.eligibility import evaluate_all, evaluate_cancellation, evaluate_exchange, evaluate_return, replacement_sizes  # noqa: E402
from src.support.entities import extract_entities  # noqa: E402
from src.support.urgency import text_urgency  # noqa: E402

SEED = 20260920
N_PRODUCTS, N_CUSTOMERS, N_ORDERS, N_CONVERSATIONS = 1000, 2000, 10000, 5000
N_UNSEEN = 600
OUT = ROOT / "data" / "synthetic"
NOW = config.DEMO_NOW

DEMO_CUSTOMER_INDEX = 42
SHOWCASE_PRODUCT_INDEX = 500

BRANDS = ["Urbanloom", "Northbay", "Threadwell", "Loomstone", "Aarav & Co", "Sundara", "Kestrel Lane", "Fablane", "Nimbus Wear", "Coastline", "Indigo Row", "Marigold Mills"]
COLORS = ["Black", "White", "Navy", "Olive", "Grey", "Maroon", "Beige", "Blue", "Red", "Mustard", "Teal", "Pink"]
STYLES = ["Solid", "Printed", "Striped", "Checked", "Slim Fit", "Regular Fit", "Relaxed Fit", "Textured"]
# (category, singular, genders, size kind, price range, weight)
CATEGORIES = [
    ("T-Shirts", "t-shirt", ["Men", "Women", "Unisex"], "apparel", (399, 1499), 16),
    ("Shirts", "shirt", ["Men", "Women"], "apparel", (699, 2299), 10),
    ("Jeans", "jeans", ["Men", "Women"], "waist", (999, 2999), 10),
    ("Trousers", "trousers", ["Men", "Women"], "waist", (899, 2499), 7),
    ("Kurtas", "kurta", ["Men", "Women"], "apparel", (599, 2499), 9),
    ("Dresses", "dress", ["Women"], "apparel", (799, 3499), 9),
    ("Tops", "top", ["Women"], "apparel", (399, 1799), 8),
    ("Hoodies", "hoodie", ["Men", "Women", "Unisex"], "apparel", (899, 2799), 6),
    ("Jackets", "jacket", ["Men", "Women"], "apparel", (1499, 4999), 5),
    ("Sneakers", "sneakers", ["Men", "Women", "Unisex"], "shoe", (1299, 4999), 8),
    ("Casual Shoes", "casual shoes", ["Men", "Women"], "shoe", (999, 3499), 6),
    ("Innerwear", "innerwear set", ["Men", "Women"], "apparel", (299, 899), 6),
]
SIZES = {"apparel": ["S", "M", "L", "XL", "XXL"], "waist": ["28", "30", "32", "34", "36"], "shoe": ["6", "7", "8", "9", "10", "11"]}

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Kabir", "Ishaan", "Neha", "Priya", "Ananya", "Diya", "Kavya", "Meera", "Riya", "Saanvi", "Tara", "Zoya", "Isha", "Nikhil", "Rahul", "Sneha", "Pooja", "Karan", "Varun", "Sanjay", "Anjali", "Divya", "Manish", "Deepak", "Shreya"]
LAST_NAMES = ["Mehta", "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Patel", "Gupta", "Singh", "Kapoor", "Joshi", "Rao", "Menon", "Das", "Bose", "Malhotra", "Chopra", "Khan", "Pillai", "Desai"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Kochi", "Chandigarh", "Indore", "Bhopal", "Nagpur"]
HUBS = ["Bengaluru Hub", "Mumbai Hub", "Delhi Hub", "Hyderabad Hub", "Kolkata Hub", "Chennai Hub", "Pune Hub"]
CARRIERS = ["Swiftline", "BlueKart", "DeliverEase", "RoadRunner"]
PAYMENT_METHODS = ["UPI", "Card", "COD", "NetBanking", "Wallet"]
PAYMENT_WEIGHTS = [42, 25, 20, 8, 5]

RETURN_WINDOW_DAYS = config.RETURN_WINDOW_DAYS


def iso(dt):
    return dt.replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ products
def stock_for(rng, sizes):
    return {s: (0 if rng.random() < 0.12 else rng.randint(1, 15)) for s in sizes}


def make_products(rng):
    weights = [c[5] for c in CATEGORIES]
    products = []
    for i in range(1, N_PRODUCTS + 1):
        category, singular, genders, kind, (lo, hi), _ = rng.choices(CATEGORIES, weights)[0]
        brand, color = rng.choice(BRANDS), rng.choice(COLORS)
        gender, style = rng.choice(genders), rng.choice(STYLES)
        mrp = rng.randrange(lo, hi + 1, 50) + 49
        discount = rng.choice([0, 10, 15, 20, 25, 30, 40, 50])
        price = max(299, int(mrp * (100 - discount) / 100 / 10) * 10 - 1)
        returnable = category != "Innerwear" and rng.random() > 0.03
        sizes = SIZES[kind]
        products.append(
            {
                "product_id": f"PRD-DEMO-{i:04d}",
                "name": f"{brand} {gender} {style} {color} {singular.title()}",
                "brand": brand,
                "category": category,
                "singular": singular,
                "gender": gender,
                "color": color,
                "fit": style,
                "mrp": mrp,
                "price": price,
                "discount_pct": discount,
                "sizes": sizes,
                "stock_by_size": stock_for(rng, sizes),
                "returnable": returnable,
                "exchangeable": returnable,
            }
        )
    # The showcase product used by the demo order MYN-DEMO-004281.
    products[SHOWCASE_PRODUCT_INDEX - 1].update(
        {
            "name": "Urbanloom Men Solid Black T-Shirt",
            "brand": "Urbanloom",
            "category": "T-Shirts",
            "singular": "t-shirt",
            "gender": "Men",
            "color": "Black",
            "fit": "Solid",
            "mrp": 1499,
            "price": 999,
            "discount_pct": 33,
            "sizes": SIZES["apparel"],
            "stock_by_size": {"S": 12, "M": 4, "L": 9, "XL": 6, "XXL": 0},
            "returnable": True,
            "exchangeable": True,
        }
    )
    return products


# ----------------------------------------------------------------- customers
def make_customers(rng):
    customers = []
    for i in range(1, N_CUSTOMERS + 1):
        first, last, city = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES), rng.choice(CITIES)
        joined = NOW - timedelta(days=rng.randint(30, 2500))
        customers.append(
            {
                "customer_id": f"CUST-DEMO-{i:05d}",
                "name": f"{first} {last}",
                "email": f"{first}.{last}.{i}@example.com".lower(),
                "phone_masked": f"+91-XXXXXX{rng.randint(1000, 9999)}",
                "city": city,
                "tier": "premium" if rng.random() < 0.15 else "standard",
                "joined_date": joined.date().isoformat(),
            }
        )
    customers[DEMO_CUSTOMER_INDEX - 1].update({"name": "Muskan Suman", "email": "muskan.suman.42@example.com", "city": "Bengaluru", "tier": "premium"})
    return customers


# -------------------------------------------------------------------- orders
def stage_events(rng, city, stages):
    """stages: list of (label, datetime); keeps only events that already happened."""
    hub = rng.choice(HUBS)
    location = {"ORDER_PLACED": "Online", "CONFIRMED": "Warehouse", "PACKED": "Warehouse", "SHIPPED": hub, "OUT_FOR_DELIVERY": f"{city} Delivery Centre", "DELIVERED": city, "CANCELLED": "Online", "RETURN_PICKUP_SCHEDULED": city, "RETURN_RECEIVED": "Returns Warehouse"}
    return [{"timestamp": iso(ts), "status": label, "location": location.get(label, hub)} for label, ts in stages if ts <= NOW]


def build_order(idx, rng, product, customer, spec=None):
    spec = spec or {}
    method = spec.get("method") or rng.choices(PAYMENT_METHODS, PAYMENT_WEIGHTS)[0]
    prepaid = method != "COD"
    size = spec.get("size") or rng.choice(product["sizes"])

    scenario = spec.get("scenario")
    if "delivery_dt" in spec:
        transit = 5
        delivery_dt = spec["delivery_dt"]
        order_dt = delivery_dt - timedelta(days=transit)
        age = (NOW - order_dt).total_seconds() / 86400
    elif "order_dt" in spec:
        order_dt = spec["order_dt"]
        age = (NOW - order_dt).total_seconds() / 86400
        transit = 5
        delivery_dt = order_dt + timedelta(days=transit)
    else:
        age = rng.uniform(0, 120)
        order_dt = NOW - timedelta(days=age)
        transit = rng.randint(3, 7)
        delivery_dt = order_dt + timedelta(days=transit, hours=rng.randint(0, 10))

    if scenario is None:
        r = rng.random()
        returnable = product["returnable"]
        if r < 0.05 and age > 0.1:
            scenario = "cancelled"
        elif r < 0.08 and 8 <= age <= 20:
            scenario = "delayed"
        elif age >= 14 and returnable and r < 0.13:
            scenario = "returned"
        elif age >= 14 and returnable and r < 0.15:
            scenario = "return_initiated"
        elif age >= 14 and returnable and r < 0.17:
            scenario = "exchange_initiated"
        else:
            scenario = "standard"

    t_conf, t_pack = order_dt + timedelta(hours=2), order_dt + timedelta(hours=12)
    t_ship = order_dt + timedelta(days=1, hours=rng.randint(0, 6))
    stages = [("ORDER_PLACED", order_dt), ("CONFIRMED", t_conf), ("PACKED", t_pack)]

    delivered_dt = cancelled_dt = return_dt = refund_init = expected = None
    status = "placed"
    refund_completed = False

    if scenario == "cancelled":
        cancelled_dt = spec.get("cancelled_dt") or min(order_dt + timedelta(hours=rng.randint(1, 20)), NOW - timedelta(minutes=5))
        stages = [s for s in stages if s[1] <= cancelled_dt] + [("CANCELLED", cancelled_dt)]
        status = "cancelled"
    elif scenario == "delayed":
        expected = order_dt + timedelta(days=5)
        stages += [("SHIPPED", t_ship)]
        status = "shipped"
    else:
        expected = order_dt + timedelta(days=transit)
        t_ofd = delivery_dt - timedelta(hours=8)
        stages += [("SHIPPED", t_ship), ("OUT_FOR_DELIVERY", t_ofd), ("DELIVERED", delivery_dt)]
        if NOW < t_conf:
            status = "placed"
        elif NOW < t_pack:
            status = "confirmed"
        elif NOW < t_ship:
            status = "packed"
        elif NOW < t_ofd:
            status = "shipped"
        elif NOW < delivery_dt:
            status = "out_for_delivery"
        else:
            status = "delivered"
            delivered_dt = delivery_dt
            if scenario in ("returned", "return_initiated", "exchange_initiated"):
                span = max(1.0, min(8.0, (NOW - delivery_dt).total_seconds() / 86400 - 1))
                return_dt = delivery_dt + timedelta(days=rng.uniform(1, span))
                stages.append(("RETURN_PICKUP_SCHEDULED", return_dt))
                if scenario == "returned" and return_dt + timedelta(days=5) <= NOW:
                    status = "returned"
                    stages.append(("RETURN_RECEIVED", return_dt + timedelta(days=5)))
                else:
                    status = "return_initiated" if scenario != "exchange_initiated" else "exchange_initiated"

    events = stage_events(rng, customer["city"], stages)

    # ---- payment
    if status == "cancelled":
        debited = prepaid
        if debited:
            stuck = spec.get("refund_stuck", rng.random() < 0.15)
            refund_init = None if stuck else cancelled_dt + timedelta(days=1)
            refund_completed = refund_init is not None and NOW >= refund_init + timedelta(days=5) and rng.random() > 0.06
            payment_status = "refunded" if refund_completed else "refund_pending"
            if refund_init and refund_init > NOW:
                refund_init = None
        else:
            payment_status = "not_charged"
    elif status == "returned":
        debited = True
        refund_init = return_dt + timedelta(days=5)
        refund_completed = NOW >= refund_init + timedelta(days=5) and rng.random() > 0.06
        payment_status = "refunded" if refund_completed else "refund_pending"
    elif prepaid:
        debited, payment_status = True, "paid"
    elif delivered_dt or status in ("return_initiated", "exchange_initiated"):
        debited, payment_status = True, "paid"
    else:
        debited, payment_status = False, "cod_pending"

    order = {
        "order_id": f"MYN-DEMO-{idx:06d}",
        "customer_id": customer["customer_id"],
        "product_id": product["product_id"],
        "product_name": product["name"],
        "brand": product["brand"],
        "category": product["category"],
        "size": size,
        "color": product["color"],
        "quantity": 1,
        "price": product["price"],
        "mrp": product["mrp"],
        "order_date": iso(order_dt),
        "expected_delivery_date": iso(expected) if expected else None,
        "delivery_date": iso(delivered_dt) if delivered_dt else None,
        "cancelled_date": iso(cancelled_dt) if cancelled_dt else None,
        "return_initiated_date": iso(return_dt) if return_dt else None,
        "refund_initiated_date": iso(refund_init) if refund_init else None,
        "status": status,
        "payment_method": method,
        "payment_status": payment_status,
        "amount_debited": bool(debited),
        "carrier": rng.choice(CARRIERS),
        "tracking_id": f"TRK{rng.randint(10**9, 10**10 - 1)}",
        "tracking_events": events,
    }
    order["return_eligible"] = evaluate_return(order, product)["eligible"]
    order["exchange_eligible"] = evaluate_exchange(order, product)["eligible"]
    order["cancellable"] = evaluate_cancellation(order)["eligible"]
    order["replacement_sizes"] = replacement_sizes(order, product)
    return order


def showcase_specs(products):
    non_returnable = next(i for i, p in enumerate(products, 1) if not p["returnable"])
    d = timedelta
    return {
        4281: {"product": SHOWCASE_PRODUCT_INDEX, "size": "M", "method": "UPI", "delivery_dt": NOW - d(days=4), "scenario": "standard"},
        7312: {"method": "UPI", "order_dt": NOW - d(days=9), "scenario": "delayed"},
        2210: {"method": "UPI", "order_dt": NOW - d(days=12, hours=12), "scenario": "cancelled", "cancelled_dt": NOW - d(days=12), "refund_stuck": True},
        9001: {"method": "Card", "order_dt": NOW - d(hours=6), "scenario": "standard"},
        1777: {"method": "UPI", "delivery_dt": NOW - d(days=40), "scenario": "standard"},
        5555: {"product": non_returnable, "method": "Card", "delivery_dt": NOW - d(days=9), "scenario": "standard"},
    }


def make_orders(rng, products, customers):
    demo = customers[DEMO_CUSTOMER_INDEX - 1]
    showcase = showcase_specs(products)
    orders = []
    for idx in range(1, N_ORDERS + 1):
        spec = showcase.get(idx)
        if spec:
            product, customer = products[spec.get("product", rng.randint(1, N_PRODUCTS)) - 1], demo
        else:
            product = products[rng.randrange(N_PRODUCTS)]
            customer = customers[rng.randrange(N_CUSTOMERS)]
            if customer["customer_id"] == demo["customer_id"]:
                customer = customers[DEMO_CUSTOMER_INDEX]  # keep the demo customer's orders curated
        orders.append(build_order(idx, rng, product, customer, spec))
    return orders


# ------------------------------------------------------------- conversations
def typo(rng, text):
    words = text.split(" ")
    candidates = [i for i, w in enumerate(words) if len(w) > 4 and w.isalpha()]
    if not candidates:
        return text
    i = rng.choice(candidates)
    w = words[i]
    j = rng.randrange(1, len(w) - 2)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def add_noise(rng, text, sensitive=False):
    text = rng.choice(PREFIXES) + text + rng.choice(SUFFIXES)
    if sensitive:
        text = text + rng.choice(SENSITIVE_SUFFIXES)
    if rng.random() < 0.10:
        text = typo(rng, text)
    if rng.random() < 0.25:
        text = text.lower()
    if rng.random() < 0.40:
        text = re.sub(r"[?.!]+$", "", text)
    return text.strip()


def template_pool(templates, unseen):
    return templates[-UNSEEN_PER_LIST:] if unseen else templates[:-UNSEEN_PER_LIST]


def make_conversations(rng, products, customers, orders):
    products_by_id = {p["product_id"]: p for p in products}
    customer_by_id = {c["customer_id"]: c for c in customers}
    orders_by_customer = {}
    for o in orders:
        orders_by_customer.setdefault(o["customer_id"], []).append(o)

    def relevant_pool(intent):
        return [o for o in orders if o in candidate_orders(intent, [o], products_by_id)]

    pools = {intent: relevant_pool(intent) for intent in config.INTENTS}
    kinds = list(INTENT_WEIGHTS) + ["AMBIGUOUS"]
    weights = [w * 0.94 for w in INTENT_WEIGHTS.values()] + [6]

    seen_texts = set()
    rows = []

    def generate(unseen):
        for _ in range(100):
            kind = rng.choices(kinds, weights)[0]
            ambiguous = kind == "AMBIGUOUS"
            intent = rng.choices(list(AMBIGUOUS_LABELS), list(AMBIGUOUS_LABELS.values()))[0] if ambiguous else kind
            table = AMBIGUOUS if ambiguous else TEMPLATES[intent]

            wants_order = ambiguous or intent in config.ORDER_DEPENDENT_INTENTS or intent == "SIZE_ISSUE"
            order = None
            if wants_order and intent not in ("HUMAN_AGENT", "GENERAL_QUERY"):
                pool_intent = "DAMAGED_PRODUCT" if ambiguous else intent
                pool = pools.get(pool_intent) if rng.random() < 0.75 else None
                order = rng.choice(pool) if pool else rng.choice(orders)
            elif intent == "HUMAN_AGENT" and "with_id" in table and rng.random() < 0.2:
                order = rng.choice(orders)

            with_id = order is not None and "with_id" in table and rng.random() < 0.6
            key = "with_id" if with_id else "no_id"
            if key not in table:
                key, with_id = "no_id", False
            pool_templates = template_pool(table[key], unseen)
            if not pool_templates:
                continue
            template = rng.choice(pool_templates)

            product = products_by_id[order["product_id"]] if order else rng.choice(products)
            size = None
            if "{size}" in template:
                options = [s for s in product["sizes"] if not order or s != order["size"]]
                size = rng.choice(options)
            item = f"{product['color'].lower()} {product['singular']}"
            text = template.format(oid=order["order_id"] if with_id else "", size=size or "", item=item)
            sensitive = (not ambiguous) and intent != "HUMAN_AGENT" and rng.random() < 0.03
            text = add_noise(rng, text, sensitive)
            if text.lower() in seen_texts:
                continue
            seen_texts.add(text.lower())

            customer_id = order["customer_id"] if order else rng.choice(customers)["customer_id"]
            entities = extract_entities(text)
            gold_confidence = 0.5 if ambiguous else 0.95
            urgency = text_urgency("DAMAGED_PRODUCT" if ambiguous else intent, text)

            customer_orders = orders_by_customer.get(customer_id, [])
            if entities.get("order_id"):
                ctx_order = next((o for o in customer_orders if o["order_id"] == entities["order_id"]), None)
                candidates = []
            else:
                ctx_order, candidates = resolve_order(intent, text, customer_orders, products_by_id)
            evaluation = evaluate_all(ctx_order, products_by_id[ctx_order["product_id"]], entities.get("requested_size")) if ctx_order else None
            decision = decide(
                intent=intent,
                confidence=gold_confidence,
                text=text,
                order=ctx_order,
                evaluation=evaluation,
                requested_size=entities.get("requested_size"),
                order_id_not_found=entities.get("order_id") if entities.get("order_id") and not ctx_order else None,
                candidate_orders=candidates,
            )
            return {
                "customer_id": customer_id,
                "order_id": order["order_id"] if with_id else None,
                "text": text,
                "intent": intent,
                "urgency": urgency,
                "requested_size": entities.get("requested_size"),
                "ambiguous": ambiguous,
                "sensitive": sensitive,
                "expected_decision": decision["action"],
                "expected_outcome": decision["outcome"],
                "escalation_needed": decision["action"] == "HUMAN_ESCALATION",
                "template_group": "unseen" if unseen else "seen",
            }
        raise RuntimeError("could not generate a unique conversation")

    seen_rows = [generate(False) for _ in range(N_CONVERSATIONS - N_UNSEEN)]
    unseen_rows = [generate(True) for _ in range(N_UNSEEN)]

    rng.shuffle(seen_rows)
    n = len(seen_rows)
    cut_train, cut_val = int(n * 0.70), int(n * 0.80)
    for i, row in enumerate(seen_rows):
        row["split"] = "train" if i < cut_train else "val" if i < cut_val else "test"
    for row in unseen_rows:
        row["split"] = "test_unseen"

    rows = seen_rows + unseen_rows
    rng.shuffle(rows)
    for i, row in enumerate(rows, 1):
        row["conversation_id"] = f"CONV-DEMO-{i:05d}"
    return [{"conversation_id": r.pop("conversation_id"), **r} for r in rows]


# -------------------------------------------------------------------- output
def write_json(path, data):
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def write_csv(path, rows):
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def main():
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    products = make_products(rng)
    customers = make_customers(rng)
    orders = make_orders(rng, products, customers)
    conversations = make_conversations(rng, products, customers, orders)

    for name, rows in [("products", products), ("customers", customers), ("orders", orders), ("support_conversations", conversations)]:
        write_json(OUT / f"{name}.json", rows)
        write_csv(OUT / f"{name}.csv", rows)

    kb_dir = OUT / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)
    for filename, body in KB_DOCUMENTS.items():
        (kb_dir / filename).write_text(body)

    meta = {
        "seed": SEED,
        "demo_now": iso(NOW),
        "demo_customer_id": customers[DEMO_CUSTOMER_INDEX - 1]["customer_id"],
        "counts": {"products": len(products), "customers": len(customers), "orders": len(orders), "support_conversations": len(conversations), "knowledge_base": len(KB_DOCUMENTS)},
        "notice": "All data is synthetic and created for demonstration purposes.",
    }
    write_json(OUT / "meta.json", meta)
    print(json.dumps(meta["counts"]))


if __name__ == "__main__":
    main()
