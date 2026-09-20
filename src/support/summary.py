"""Customer-facing outcome summary, built only from the decision, the order
record and the rule results: no model involved.

The chat reply is prose; this is the same result as structured facts the UI
can lay out (headline, why, what happens next, refund, reference). Diagnostic
detail (intent, confidence, workflow) stays in the AI-details view.
"""
from src.support import config
from src.support.messages import day, money

# outcome -> (headline, tone, evaluation part that explains it)
_OUTCOMES = {
    "RETURN_APPROVED": ("Return approved", "success", "return"),
    "RETURN_DENIED": ("Return not available", "warning", "return"),
    "EXCHANGE_APPROVED": ("Exchange approved", "success", "exchange"),
    "EXCHANGE_DENIED": ("Exchange not available", "warning", "exchange"),
    "CANCELLATION_APPROVED": ("Order cancelled", "success", "cancellation"),
    "CANCELLATION_DENIED": ("Order can't be cancelled", "warning", "cancellation"),
    "REFUND_IN_PROGRESS": ("Refund on its way", "info", None),
    "REFUND_AFTER_RETURN": ("Refund follows a return", "info", "return"),
    "REFUND_NOT_AVAILABLE": ("No refund due", "neutral", None),
    "REFUND_OVERDUE": ("Refund is overdue", "escalated", None),
    "PAYMENT_REFUND_IN_PROGRESS": ("Refund on its way", "info", None),
    "PAYMENT_DISPUTE": ("Payment dispute escalated", "escalated", None),
    "PAYMENT_UNVERIFIED": ("Payment check escalated", "escalated", None),
    "DAMAGED_PICKUP_OFFERED": ("Pickup arranged", "success", "report"),
    "WRONG_ITEM_PICKUP_OFFERED": ("Pickup arranged", "success", "report"),
    "POLICY_EXCEPTION": ("Needs a policy exception", "escalated", "report"),
    "DELIVERED_BUT_NOT_RECEIVED": ("Delivery investigation escalated", "escalated", None),
    "SHIPMENT_LOST_RISK": ("Shipment investigation escalated", "escalated", None),
    "TRACKING_PROVIDED": (None, "info", None),
    "DELIVERY_STATUS_PROVIDED": (None, "info", None),
    "HUMAN_REQUESTED": ("Human support escalation prepared", "escalated", None),
    "SENSITIVE_LANGUAGE": ("Human support escalation prepared", "escalated", None),
    "LOW_CONFIDENCE": ("Human support escalation prepared", "escalated", None),
}


def _refund(order, timeline):
    return {"amount": money(order["price"]), "method": f"Original payment method ({order['payment_method']})", "timeline": timeline}


def _steps_and_refund(outcome, order, evaluation, requested_size):
    sla = config.REFUND_SLA_DAYS
    if outcome == "RETURN_APPROVED":
        return (
            ["Pickup is scheduled within 2 business days at your delivery address", "The item is checked when it reaches us", "Your refund starts after that check"],
            _refund(order, f"Within {sla} days of the refund starting"),
        )
    if outcome == "RETURN_DENIED":
        return (["A human agent can review this if you think it's a mistake"], None)
    if outcome == "EXCHANGE_APPROVED":
        return ([f"Size {requested_size} is reserved for you", "The original item is picked up", f"Size {requested_size} ships once the original is picked up", "No extra charge"], None)
    if outcome == "EXCHANGE_DENIED":
        step = "A return may still be possible while you're inside the return window" if evaluation["return"]["eligible"] else "A human agent can review this if you think it's a mistake"
        return ([step], None)
    if outcome == "CANCELLATION_APPROVED":
        paid = order["payment_status"] == "paid"
        return (["The order will not be shipped"] + ([f"Any prepaid amount is refunded within {sla} days"] if paid else []), _refund(order, f"Within {sla} days") if paid else None)
    if outcome == "CANCELLATION_DENIED":
        step = "You can return the item once it is delivered" if order["status"] != "delivered" else f"You can return it within {config.RETURN_WINDOW_DAYS} days of delivery"
        return ([step], None)
    if outcome == "REFUND_IN_PROGRESS":
        due = evaluation["refund"]["details"].get("expected_by")
        return ([f"Your refund is expected by {day(due)}"], _refund(order, f"Expected by {day(due)}"))
    if outcome == "PAYMENT_REFUND_IN_PROGRESS":
        due = evaluation["payment"]["expected_by"]
        return ([f"Your refund is expected by {day(due)}"], _refund(order, f"Expected by {day(due)}"))
    if outcome == "REFUND_AFTER_RETURN":
        return (["Refunds for delivered items are issued after the returned item is received", "Start a return to begin the refund"], None)
    if outcome == "REFUND_NOT_AVAILABLE":
        return (["Nothing is pending on this order and it isn't eligible for a return"], None)
    if outcome in ("REFUND_OVERDUE", "PAYMENT_DISPUTE"):
        due = evaluation["payment"]["expected_by"] if outcome == "PAYMENT_DISPUTE" else evaluation["refund"]["details"].get("expected_by")
        return (["A human-support escalation was prepared to chase the payment", "This is a demo, so no real agent is connected"], _refund(order, f"Was due by {day(due)}"))
    if outcome == "DAMAGED_PICKUP_OFFERED":
        return (["A free pickup is arranged", "Choose a replacement or a full refund", "Photos of the damage help speed this up"], None)
    if outcome == "WRONG_ITEM_PICKUP_OFFERED":
        return (["A free pickup is arranged", "The correct item is sent, or you are refunded if it is out of stock"], None)
    if outcome in ("TRACKING_PROVIDED", "DELIVERY_STATUS_PROVIDED"):
        delivery = evaluation["delivery"]
        if order["status"] == "delivered":
            return ([f"Delivered on {day(order['delivery_date'])}"], None)
        steps = [f"Expected by {day(order['expected_delivery_date'])}"]
        if delivery["delayed"]:
            steps.append(f"Running {delivery['delayed_days']} days late")
        return (steps + [f"Carrier: {order['carrier']}, tracking ID {order['tracking_id']}"], None)
    return (["A human-support escalation was prepared for this case", "This is a demo, so no real agent is connected"], None)


def customer_summary(decision, order, evaluation, demo_action, requested_size):
    """Return the structured customer summary, or None when there is nothing to summarise."""
    outcome = decision["outcome"]
    if outcome not in _OUTCOMES:
        return None
    escalation_only = outcome in ("HUMAN_REQUESTED", "SENSITIVE_LANGUAGE", "LOW_CONFIDENCE")
    if order is None and not escalation_only:
        return None

    title, tone, part = _OUTCOMES[outcome]
    if title is None:
        title = "Order " + order["status"].replace("_", " ")
    if outcome == "EXCHANGE_APPROVED":
        title = f"Exchange approved for size {requested_size}"

    if escalation_only:
        steps, refund = ["Your conversation context is included, so you won't need to repeat yourself", "This is a demo, so no real agent is connected"], None
    else:
        steps, refund = _steps_and_refund(outcome, order, evaluation, requested_size)

    checks = evaluation[part]["checks"] if part and evaluation and part in evaluation else []
    why = [{"text": f"{c['name']}: {c['detail']}", "passed": c["passed"]} for c in checks]
    if not why and tone in ("warning", "escalated"):
        why = [{"text": decision["reason"], "passed": False}]

    heading = {"success": "Why this was allowed", "warning": "Why this isn't available", "escalated": "Why this was escalated"}.get(tone)

    return {
        "title": title,
        "tone": tone,
        "why_heading": heading,
        "why": why,
        "next_steps": steps,
        "refund": refund,
        "reference": demo_action["reference"] if demo_action else None,
        "order_id": order["order_id"] if order else None,
    }
