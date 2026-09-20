"""HTTP endpoints for the support demo.

Structured lookups (orders, products, customers) are plain repository reads.
`/support/resolve` runs the full pipeline. Everything is synthetic data.
"""
import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config import ROOT_DIR
from src.support import config
from src.support.catalog import SORTS, Catalog
from src.support.eligibility import evaluate_all
from src.support.knowledge import KB_DIR, load_chunks
from src.support.pipeline import DEMO_NOTICE, DETAIL_OPTION_INTENTS

router = APIRouter()
_pipeline = None
_catalog = None

EVALUATION_FILE = ROOT_DIR / "evaluation" / "results.json"

DEMO_SCENARIOS = [
    {"id": "track", "title": "Track order", "message": "Where is my order MYN-DEMO-004281?"},
    {"id": "exchange", "title": "Exchange", "message": "I received the wrong size and want to exchange it."},
    {"id": "return", "title": "Return", "message": "I want to return my recent order."},
    {"id": "refund", "title": "Refund", "message": "I want a refund for my order."},
    {"id": "payment", "title": "Payment issue", "message": "I was charged but my order was cancelled."},
    {"id": "delivery", "title": "Delivery issue", "message": "My order hasn't arrived yet."},
    {"id": "damaged", "title": "Damaged product", "message": "My product arrived damaged."},
    {"id": "wrong", "title": "Wrong product", "message": "I received a different product than what I ordered."},
    {"id": "human", "title": "Human support", "message": "I want to talk to a human agent."},
    {"id": "ambiguous", "title": "Ambiguous query", "message": "My product isn't right."},
]


def set_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


def _store():
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Support pipeline is still starting up")
    return _pipeline.store


def _catalog_for_store():
    global _catalog
    if _catalog is None:
        _catalog = Catalog(_store())
    return _catalog


class ResolveRequest(BaseModel):
    message: str
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    selected_size: Optional[str] = None
    clarification_attempts: int = 0
    intent_override: Optional[str] = None


def _validated(req):
    _store()
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is empty")
    if req.intent_override and req.intent_override not in config.INTENTS:
        raise HTTPException(status_code=422, detail=f"Unknown intent '{req.intent_override}'")
    return message[:1000]


def _run(req, message, on_step=None):
    return _pipeline.resolve(
        message,
        customer_id=req.customer_id,
        order_id=req.order_id,
        selected_size=req.selected_size,
        clarification_attempts=req.clarification_attempts,
        intent_override=req.intent_override,
        on_step=on_step,
    )


@router.post("/support/resolve")
def resolve(req: ResolveRequest):
    return _run(req, _validated(req))


@router.post("/support/resolve/stream")
def resolve_stream(req: ResolveRequest):
    """Server-sent events: one `step` event as each pipeline stage really
    finishes, then a final `result` (or `error`)."""
    message = _validated(req)
    events = queue.Queue()

    def work():
        try:
            events.put(("result", _run(req, message, on_step=lambda step: events.put(("step", step)))))
        except Exception as exc:
            events.put(("error", {"detail": f"{type(exc).__name__}: {exc}"}))
        events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield f"event: {item[0]}\ndata: {json.dumps(item[1])}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/support/meta")
def meta():
    store = _store()
    demo = store.get_customer(store.demo_customer_id)
    return {
        "notice": DEMO_NOTICE,
        "about": "All customer, product and order information shown in this demo is synthetic data created for demonstration purposes. Nothing here is connected to a real store.",
        "demo_customer": {"customer_id": demo["customer_id"], "name": demo["name"], "email": demo["email"], "city": demo["city"], "tier": demo["tier"]},
        "policy_windows": {"return_days": config.RETURN_WINDOW_DAYS, "exchange_days": config.EXCHANGE_WINDOW_DAYS, "report_days": config.REPORT_WINDOW_DAYS, "refund_days": config.REFUND_SLA_DAYS},
        "demo_clock": store.meta["demo_now"],
        "counts": store.meta["counts"],
        "intents": list(config.INTENTS),
        "detail_options": [{"value": key, "label": label, "intent": DETAIL_OPTION_INTENTS[key]} for key, label in [("damaged", "The item is damaged"), ("wrong_item", "I got the wrong item"), ("size", "The size or fit is wrong"), ("other", "Something else")]],
        "confidence_thresholds": {"high": config.HIGH_CONFIDENCE, "medium": config.MEDIUM_CONFIDENCE},
        "classifier_source": getattr(_pipeline, "classifier_source", "unknown"),
        "llm_enabled": _pipeline.llm is not None,
    }


@router.get("/support/scenarios")
def scenarios():
    return DEMO_SCENARIOS


@router.get("/support/knowledge")
def knowledge():
    """The policy documents behind the Help Center panel."""
    docs = {}
    for chunk in load_chunks(KB_DIR):
        doc = docs.setdefault(chunk["doc_id"], {"id": chunk["doc_id"], "title": chunk["title"], "sections": []})
        doc["sections"].append({"heading": chunk["section"], "text": chunk["text"].split("\n", 1)[1]})
    return list(docs.values())


@router.get("/support/evaluation")
def evaluation():
    if not EVALUATION_FILE.exists():
        raise HTTPException(status_code=404, detail="The evaluation has not been run yet. Run `python scripts/evaluate_support.py`.")
    return json.loads(EVALUATION_FILE.read_text())


def _owned_order(order_id, customer_id):
    """Fetch an order; when a customer_id is given, other customers' orders read as not found."""
    order = _store().get_order(order_id.upper())
    if order is None or (customer_id and order["customer_id"] != customer_id.upper()):
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order


@router.get("/orders/{order_id}")
def get_order(order_id: str, customer_id: Optional[str] = None):
    order = _owned_order(order_id, customer_id)
    return {k: v for k, v in order.items() if k != "tracking_events"}


@router.get("/orders/{order_id}/tracking")
def get_tracking(order_id: str, customer_id: Optional[str] = None):
    order = _owned_order(order_id, customer_id)
    return {"order_id": order["order_id"], "status": order["status"], "carrier": order["carrier"], "tracking_id": order["tracking_id"], "expected_delivery_date": order["expected_delivery_date"], "events": order["tracking_events"]}


@router.get("/orders/{order_id}/eligibility")
def get_eligibility(order_id: str, requested_size: Optional[str] = None, customer_id: Optional[str] = None):
    order = _owned_order(order_id, customer_id)
    return evaluate_all(order, _store().get_product(order["product_id"]), requested_size)


@router.get("/products/{product_id}")
def get_product(product_id: str):
    product = _store().get_product(product_id.upper())
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    customer = _store().get_customer(customer_id.upper())
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


ORDER_LIST_FIELDS = ("order_id", "product_id", "product_name", "brand", "category", "color", "size", "price", "mrp", "status", "order_date", "delivery_date", "expected_delivery_date", "cancelled_date", "payment_status")
IN_TRANSIT = {"placed", "confirmed", "packed", "shipped", "out_for_delivery"}


def _order_actions(order, product):
    """Which buttons make sense, straight from the eligibility rules."""
    elig = evaluate_all(order, product)
    return {
        "track": order["status"] in IN_TRANSIT or order["status"] == "delivered",
        "return": elig["return"]["eligible"],
        "exchange": elig["exchange"]["eligible"],
        "cancel": elig["cancellation"]["eligible"],
    }


@router.get("/customers/{customer_id}/orders")
def get_customer_orders(customer_id: str, limit: int = Query(20, ge=1, le=200)):
    store = _store()
    if store.get_customer(customer_id.upper()) is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    rows = []
    for o in store.customer_orders(customer_id.upper())[:limit]:
        row = {k: o[k] for k in ORDER_LIST_FIELDS}
        row["actions"] = _order_actions(o, store.get_product(o["product_id"]))
        rows.append(row)
    return rows


@router.get("/shop/products")
def shop_products(
    q: Optional[str] = Query(None, max_length=100),
    gender: Optional[str] = None,
    category: list[str] = Query(default=[]),
    brand: list[str] = Query(default=[]),
    color: list[str] = Query(default=[]),
    size: list[str] = Query(default=[]),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    sort: str = "relevance",
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {', '.join(SORTS)}")
    return _catalog_for_store().search(q, gender, category, brand, color, size, min_price, max_price, sort, limit, offset)


@router.get("/shop/facets")
def shop_facets():
    return _catalog_for_store().facets()
