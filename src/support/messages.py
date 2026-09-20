"""Deterministic response text for every decision outcome.

These are the fallback when the LLM is unavailable, and the exact wording for
clarifications and escalations (no need for a model to improvise a handoff).
Every value interpolated here comes from the order record or the rule results.
"""
from datetime import datetime

from src.support import config

_REASONS = {
    "return_window_expired": "the {days:.0f} days since delivery are past the {window}-day return window",
    "product_not_returnable": "this type of item cannot be returned for hygiene reasons",
    "return_already_initiated": "a return is already open on this order",
    "exchange_in_progress": "an exchange is already open on this order",
    "not_delivered": "it hasn't been delivered yet",
    "exchange_window_expired": "the {days:.0f} days since delivery are past the {window}-day exchange window",
    "product_not_exchangeable": "this item isn't available for exchange",
    "no_replacement_sizes": "no other size is currently in stock",
    "already_in_progress": "a return or exchange is already open on this order",
    "already_cancelled": "it was already cancelled",
    "already_shipped": "it has already shipped",
}


def money(amount):
    return f"₹{amount:,.0f}"


def day(iso):
    return datetime.fromisoformat(iso).strftime("%d %b %Y") if iso else "soon"


def _reason(code, evaluation_part):
    days = evaluation_part.get("details", {}).get("days_since_delivery", 0)
    template = _REASONS.get(code, code.replace("_", " "))
    return template.format(days=days, window=config.RETURN_WINDOW_DAYS if "return" in code else config.EXCHANGE_WINDOW_DAYS)


def _status_line(order):
    status = order["status"]
    if status == "delivered":
        return f"was delivered on {day(order['delivery_date'])}"
    if status == "out_for_delivery":
        return f"is out for delivery and expected by {day(order['expected_delivery_date'])}"
    if status == "shipped":
        return f"has shipped and is expected by {day(order['expected_delivery_date'])}"
    if status in ("placed", "confirmed", "packed"):
        return f"is {status} and hasn't shipped yet (expected by {day(order['expected_delivery_date'])})"
    return f"is currently '{status.replace('_', ' ')}'"


def render(decision, order=None, evaluation=None, requested_size=None, demo_action=None):
    outcome = decision["outcome"]
    ref = f" Reference: {demo_action['reference']} (demo, simulated)." if demo_action else ""

    if decision["action"] == "CLARIFICATION_REQUIRED":
        return decision["clarification"]["question"]

    if outcome == "HUMAN_REQUESTED":
        return "I can help with that. I've prepared a human-support escalation and included this conversation's context, so you won't need to repeat yourself. This is a demo, so no real agent is connected."
    if outcome == "SENSITIVE_LANGUAGE":
        return "I'm sorry this has been frustrating. I've prepared a human-support escalation so a person can review your case properly. This is a demo, so no real agent is connected."
    if outcome == "LOW_CONFIDENCE":
        return "I still can't tell exactly what you need, so I've prepared a human-support escalation rather than guessing."

    if order is None:
        if outcome == "SIZE_GUIDANCE":
            return "Compare your measurements with the size chart on the product page. If you're between two sizes, choose the larger for a relaxed fit. Within 10 days of delivery you can exchange for another size that is in stock."
        return "I can help with tracking, returns, exchanges, refunds, cancellations, delivery and payment problems. Tell me what happened, and include your order ID if you have it."

    name, oid = order["product_name"], order["order_id"]

    if outcome == "TRACKING_PROVIDED":
        return f"Your order {oid} ({name}) {_status_line(order)}. Tracking ID: {order['tracking_id']} with {order['carrier']}."
    if outcome == "DELIVERY_STATUS_PROVIDED":
        d = evaluation["delivery"]
        late = f" It is {d['delayed_days']} days past its expected date, and I'm sorry for the delay." if d["delayed"] else ""
        return f"Your order {oid} {_status_line(order)}.{late}"
    if outcome == "DELIVERED_BUT_NOT_RECEIVED":
        return f"Tracking shows order {oid} {_status_line(order)}, but you haven't received it. I've prepared a human-support escalation so the courier's delivery proof can be checked."
    if outcome == "SHIPMENT_LOST_RISK":
        d = evaluation["delivery"]
        return f"Order {oid} is {d['delayed_days']} days past its expected delivery date, so it may be lost. I've prepared a human-support escalation to investigate with the courier."

    if outcome == "RETURN_APPROVED":
        days = evaluation["return"]["details"]["days_since_delivery"]
        return f"Your {name} (order {oid}) is eligible for return: it was delivered {days:.0f} days ago, inside the {config.RETURN_WINDOW_DAYS}-day window. A pickup is scheduled within 2 business days, and the refund starts once the item passes the quality check.{ref}"
    if outcome == "RETURN_DENIED":
        return f"I can't start a return for order {oid} because {_reason(evaluation['return']['reason'], evaluation['return'])}. If you think this is a mistake I can connect you with a human agent."

    if outcome == "EXCHANGE_APPROVED":
        return f"Your {name} (order {oid}) can be exchanged for size {requested_size}, which is in stock, at no extra charge. The new size ships as soon as the original is picked up.{ref}"
    if outcome == "EXCHANGE_DENIED":
        return f"I can't exchange order {oid} because {_reason(evaluation['exchange']['reason'], evaluation['exchange'])}. A return may still be possible if you're inside the return window."

    if outcome == "REFUND_IN_PROGRESS":
        d = evaluation["refund"]["details"]
        return f"A refund of {money(order['price'])} for order {oid} is already on its way to your original payment method, expected by {day(d.get('expected_by'))}."
    if outcome == "REFUND_OVERDUE":
        return f"Your refund of {money(order['price'])} for order {oid} should have arrived by now. I've prepared a human-support escalation to chase it with the payment provider."
    if outcome == "REFUND_AFTER_RETURN":
        return f"Refunds for delivered items are issued after the returned item is received. Order {oid} is eligible for return, so I can start that for you."
    if outcome == "REFUND_NOT_AVAILABLE":
        return f"I couldn't find a refund due on order {oid}. Nothing is pending, and it isn't eligible for a return."

    if outcome == "CANCELLATION_APPROVED":
        return f"Order {oid} ({name}) hasn't shipped yet, so it can be cancelled. Any prepaid amount is refunded within {config.REFUND_SLA_DAYS} days.{ref}"
    if outcome == "CANCELLATION_DENIED":
        return f"I can't cancel order {oid} because {_reason(evaluation['cancellation']['reason'], evaluation['cancellation'])}. You can return it within {config.RETURN_WINDOW_DAYS} days of delivery."

    if outcome == "PAYMENT_REFUND_IN_PROGRESS":
        p = evaluation["payment"]
        return f"Order {oid} was cancelled after you were charged, and the refund of {money(order['price'])} is in progress, expected by {day(p['expected_by'])}."
    if outcome == "PAYMENT_DISPUTE":
        p = evaluation["payment"]
        return f"You were charged {money(order['price'])} for order {oid}, which was cancelled, and the refund was due by {day(p['expected_by'])}. I've prepared a human-support escalation to raise a payment dispute."
    if outcome == "PAYMENT_UNVERIFIED":
        return f"I can't see a payment problem on order {oid}, so I've prepared a human-support escalation for the payment records to be checked."

    if outcome == "DAMAGED_PICKUP_OFFERED":
        return f"I'm sorry your {name} arrived damaged. Because it was reported within {config.REPORT_WINDOW_DAYS} days of delivery, I can arrange a free pickup and either a replacement or a full refund. Photos of the damage help speed this up.{ref}"
    if outcome == "WRONG_ITEM_PICKUP_OFFERED":
        return f"I'm sorry you received the wrong item for order {oid}. I can arrange a free pickup and send the correct item, or refund you if it's out of stock.{ref}"
    if outcome == "POLICY_EXCEPTION":
        return f"Order {oid} is outside the {config.REPORT_WINDOW_DAYS}-day reporting window, so this needs a policy exception. I've prepared a human-support escalation for review."

    if outcome == "SIZE_GUIDANCE":
        return f"For your {name}, compare your measurements with the size chart on the product page. If it doesn't fit, you can exchange it for another size within {config.EXCHANGE_WINDOW_DAYS} days of delivery."

    return "I can help with tracking, returns, exchanges, refunds, cancellations, delivery and payment problems."
