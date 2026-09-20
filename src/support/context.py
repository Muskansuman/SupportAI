"""Order-context resolution: which order does the customer mean?

An explicit order ID always wins. Otherwise the customer's own orders are
filtered to the ones that make sense for the intent. If exactly one fits (or
the message says "recent"/"latest"), that order is used; if several fit, the
assistant asks instead of guessing, since acting on the wrong order is worse
than one extra question.
"""
from src.support import config
from src.support.eligibility import parse_ts

RECENT_TERMS = ("recent", "latest", "last order", "most recent", "newest")


def _days_since_delivery(order, now):
    if order["status"] != "delivered" or not order.get("delivery_date"):
        return None
    return (now - parse_ts(order["delivery_date"])).total_seconds() / 86400


def _relevant(intent, order, product, now):
    status = order["status"]
    days = _days_since_delivery(order, now)

    if intent == "TRACK_ORDER":
        return status in config.IN_TRANSIT_STATUSES or status in config.CANCELLABLE_STATUSES
    if intent == "DELIVERY_ISSUE":
        return status in config.IN_TRANSIT_STATUSES
    if intent == "CANCEL_ORDER":
        return status in config.CANCELLABLE_STATUSES
    if intent == "PAYMENT_ISSUE":
        return status == "cancelled" and order.get("amount_debited") and order["payment_status"] != "refunded"
    if intent == "RETURN_REQUEST":
        return days is not None and days <= config.RETURN_WINDOW_DAYS and product["returnable"]
    if intent == "EXCHANGE_REQUEST":
        return days is not None and days <= config.EXCHANGE_WINDOW_DAYS and product["exchangeable"]
    if intent in ("DAMAGED_PRODUCT", "WRONG_PRODUCT"):
        return days is not None and days <= config.REPORT_WINDOW_DAYS
    if intent == "REFUND_REQUEST":
        if status in ("cancelled", "returned"):
            return order.get("amount_debited") and order["payment_status"] != "refunded"
        return days is not None and days <= config.RETURN_WINDOW_DAYS and product["returnable"]
    return False


def candidate_orders(intent, orders, products_by_id, now=config.DEMO_NOW):
    ranked = sorted(orders, key=lambda o: o["order_date"], reverse=True)
    return [o for o in ranked if _relevant(intent, o, products_by_id[o["product_id"]], now)]


def resolve_order(intent, text, customer_orders, products_by_id, now=config.DEMO_NOW):
    """Return (order_or_None, candidates). `customer_orders` are this customer's orders."""
    candidates = candidate_orders(intent, customer_orders, products_by_id, now)
    if not candidates:
        return None, []
    if len(candidates) == 1:
        return candidates[0], candidates
    lowered = text.lower()
    if any(term in lowered for term in RECENT_TERMS):
        return candidates[0], candidates
    return None, candidates
