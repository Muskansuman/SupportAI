"""Deterministic eligibility rules: return, exchange, cancellation, refund,
payment, delivery and damaged/wrong-item reporting.

Pure functions over plain order/product dicts (no I/O), so the dataset
generator and the live pipeline evaluate exactly the same rules. Each result
carries a list of named checks so the UI can show why something is (or isn't)
allowed rather than a bare yes/no.
"""
from datetime import datetime, timedelta

from src.support import config

OrderDict = dict
ProductDict = dict


def parse_ts(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def _check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": detail}


def _result(eligible, reason, checks, details=None):
    return {"eligible": bool(eligible), "reason": reason, "checks": checks, "details": details or {}}


def _days_since(ts, now):
    return (now - parse_ts(ts)).total_seconds() / 86400


def replacement_sizes(order: OrderDict, product: ProductDict):
    """Sizes actually in stock, excluding the size already ordered."""
    stock = product.get("stock_by_size", {})
    return [s for s in product.get("sizes", []) if s != order.get("size") and stock.get(s, 0) > 0]


def evaluate_return(order, product, now=config.DEMO_NOW):
    status = order["status"]
    if status in ("return_initiated", "returned"):
        return _result(False, "return_already_initiated", [_check("No return in progress", False, f"Order is already '{status}'")])
    if status == "exchange_initiated":
        return _result(False, "exchange_in_progress", [_check("No exchange in progress", False, "An exchange is already open on this order")])

    checks = []
    delivered = status == "delivered" and order.get("delivery_date")
    checks.append(_check("Order delivered", delivered, f"Status is '{status}'"))
    if not delivered:
        return _result(False, "not_delivered", checks)

    days = _days_since(order["delivery_date"], now)
    within = days <= config.RETURN_WINDOW_DAYS
    checks.append(_check(f"Within {config.RETURN_WINDOW_DAYS}-day return window", within, f"Delivered {days:.0f} days ago"))
    if not within:
        return _result(False, "return_window_expired", checks, {"days_since_delivery": round(days, 1)})

    checks.append(_check("Product is returnable", product["returnable"], "Category allows returns" if product["returnable"] else "Not returnable for hygiene reasons"))
    if not product["returnable"]:
        return _result(False, "product_not_returnable", checks)

    return _result(True, "eligible", checks, {"days_since_delivery": round(days, 1)})


def evaluate_exchange(order, product, requested_size=None, now=config.DEMO_NOW):
    status = order["status"]
    if status in ("return_initiated", "returned", "exchange_initiated"):
        return _result(False, "already_in_progress", [_check("No return/exchange in progress", False, f"Order is already '{status}'")])

    checks = []
    delivered = status == "delivered" and order.get("delivery_date")
    checks.append(_check("Order delivered", delivered, f"Status is '{status}'"))
    if not delivered:
        return _result(False, "not_delivered", checks)

    days = _days_since(order["delivery_date"], now)
    within = days <= config.EXCHANGE_WINDOW_DAYS
    checks.append(_check(f"Within {config.EXCHANGE_WINDOW_DAYS}-day exchange window", within, f"Delivered {days:.0f} days ago"))
    if not within:
        return _result(False, "exchange_window_expired", checks, {"days_since_delivery": round(days, 1)})

    checks.append(_check("Product supports exchange", product["exchangeable"], "Exchange allowed" if product["exchangeable"] else "Exchange not offered for this item"))
    if not product["exchangeable"]:
        return _result(False, "product_not_exchangeable", checks)

    replacements = replacement_sizes(order, product)
    checks.append(_check("Replacement sizes in stock", bool(replacements), ", ".join(replacements) if replacements else "No other size is in stock"))
    if not replacements:
        return _result(False, "no_replacement_sizes", checks, {"replacement_sizes": []})

    details = {"replacement_sizes": replacements, "days_since_delivery": round(days, 1)}
    if requested_size:
        size_ok = requested_size.upper() in [r.upper() for r in replacements]
        checks.append(_check(f"Requested size {requested_size.upper()} available", size_ok, "In stock" if size_ok else f"Not in stock. Available: {', '.join(replacements)}"))
        if not size_ok:
            return _result(False, "requested_size_unavailable", checks, details)
        details["requested_size"] = requested_size.upper()

    return _result(True, "eligible", checks, details)


def evaluate_cancellation(order):
    status = order["status"]
    if status == "cancelled":
        return _result(False, "already_cancelled", [_check("Order not already cancelled", False, "Order was already cancelled")])
    ok = status in config.CANCELLABLE_STATUSES
    detail = f"Status is '{status}'" + ("" if ok else ". It has already shipped")
    return _result(ok, "eligible" if ok else "already_shipped", [_check("Order not yet shipped", ok, detail)])


def _refund_state(order, now):
    """Refund progress for a cancelled or returned prepaid order."""
    if order["payment_status"] == "refunded":
        return {"refund_status": "completed"}
    started = order.get("refund_initiated_date")
    anchor = order.get("cancelled_date") or order.get("return_initiated_date")
    if started:
        expected = parse_ts(started) + timedelta(days=config.REFUND_SLA_DAYS)
        status = "overdue" if now > expected else "initiated"
        return {"refund_status": status, "refund_initiated_date": started, "expected_by": expected.date().isoformat()}
    if anchor:
        expected = parse_ts(anchor) + timedelta(days=config.REFUND_SLA_DAYS)
        return {"refund_status": "overdue" if now > expected else "not_initiated", "expected_by": expected.date().isoformat()}
    return {"refund_status": "not_initiated"}


def evaluate_refund(order, product, now=config.DEMO_NOW):
    status = order["status"]
    if status in ("cancelled", "returned"):
        debited = order.get("amount_debited")
        checks = [_check("Payment captured", debited, "Amount was debited" if debited else "Nothing was charged")]
        if not debited:
            return _result(False, "no_payment_captured", checks, {"refund_status": "not_applicable"})
        state = _refund_state(order, now)
        if state["refund_status"] == "completed":
            checks.append(_check("Refund pending", False, "Refund was already completed"))
            return _result(False, "already_refunded", checks, state)
        checks.append(_check("Refund in progress", state["refund_status"] in ("initiated", "not_initiated"), f"Refund is {state['refund_status'].replace('_', ' ')}"))
        return _result(True, "refund_due", checks, state)

    ret = evaluate_return(order, product, now)
    if ret["eligible"]:
        return _result(True, "refund_after_return", ret["checks"] + [_check("Refund issued after return pickup", True, "Refund goes to the original payment method once the return is received")], {"refund_status": "after_return"})
    return _result(False, "no_refund_path", ret["checks"], {"refund_status": "not_applicable"})


def evaluate_payment(order, now=config.DEMO_NOW):
    debited = bool(order.get("amount_debited"))
    status = order["status"]
    if status == "cancelled" and debited:
        state = _refund_state(order, now)
        anomaly = state["refund_status"] != "completed"
        return {
            "debited": True,
            "anomaly": anomaly,
            "overdue": state["refund_status"] == "overdue",
            "refund_status": state["refund_status"],
            "expected_by": state.get("expected_by"),
            "payment_status": order["payment_status"],
        }
    return {"debited": debited, "anomaly": False, "overdue": False, "refund_status": "not_applicable", "expected_by": None, "payment_status": order["payment_status"]}


def evaluate_delivery(order, now=config.DEMO_NOW):
    status = order["status"]
    if status == "delivered":
        return {"state": "delivered", "delayed": False, "delayed_days": 0, "delivery_date": order.get("delivery_date")}
    if status in config.IN_TRANSIT_STATUSES:
        expected = parse_ts(order["expected_delivery_date"])
        late = max(0, int((now - expected).total_seconds() // 86400))
        return {"state": status, "delayed": now > expected, "delayed_days": late, "expected_delivery_date": order["expected_delivery_date"]}
    if status in config.CANCELLABLE_STATUSES:
        return {"state": "not_shipped", "delayed": False, "delayed_days": 0, "expected_delivery_date": order.get("expected_delivery_date")}
    return {"state": status, "delayed": False, "delayed_days": 0}


def evaluate_report(order, now=config.DEMO_NOW):
    """Damaged / wrong item can be reported within REPORT_WINDOW_DAYS of delivery."""
    delivered = order["status"] == "delivered" and order.get("delivery_date")
    checks = [_check("Order delivered", delivered, f"Status is '{order['status']}'")]
    if not delivered:
        return _result(False, "not_delivered", checks)
    days = _days_since(order["delivery_date"], now)
    ok = days <= config.REPORT_WINDOW_DAYS
    checks.append(_check(f"Reported within {config.REPORT_WINDOW_DAYS} days of delivery", ok, f"Delivered {days:.0f} days ago"))
    return _result(ok, "eligible" if ok else "report_window_expired", checks, {"days_since_delivery": round(days, 1)})


def evaluate_all(order, product, requested_size=None, now=config.DEMO_NOW):
    return {
        "return": evaluate_return(order, product, now),
        "exchange": evaluate_exchange(order, product, requested_size, now),
        "cancellation": evaluate_cancellation(order),
        "refund": evaluate_refund(order, product, now),
        "payment": evaluate_payment(order, now),
        "delivery": evaluate_delivery(order, now),
        "report": evaluate_report(order, now),
    }
