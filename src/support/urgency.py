"""Urgency rules. Urgency (how time-sensitive) is deliberately separate from
escalation (whether a human must take over): a HIGH-urgency delivery question
can still be resolved automatically, and a LOW-urgency request for a human
still goes to a person.

`text_urgency` depends only on the message text and intent, so it's a label a
model can learn from text alone. `adjust_for_context` then raises it using
facts the model never sees (a shipment that is days late, money debited for a
cancelled order).
"""
from src.support import config

_BASE = {
    "TRACK_ORDER": "LOW",
    "RETURN_REQUEST": "LOW",
    "EXCHANGE_REQUEST": "LOW",
    "REFUND_REQUEST": "MEDIUM",
    "CANCEL_ORDER": "MEDIUM",
    "DELIVERY_ISSUE": "MEDIUM",
    "PAYMENT_ISSUE": "MEDIUM",
    "DAMAGED_PRODUCT": "MEDIUM",
    "WRONG_PRODUCT": "MEDIUM",
    "SIZE_ISSUE": "LOW",
    "HUMAN_AGENT": "MEDIUM",
    "GENERAL_QUERY": "LOW",
}

_DEBIT_TERMS = ("charged", "deducted", "debited", "money was taken", "amount was taken", "double payment", "paid twice")


def _shift(level, delta):
    levels = config.URGENCY_LEVELS
    return levels[max(0, min(len(levels) - 1, levels.index(level) + delta))]


def has_sensitive_language(text):
    lowered = text.lower()
    return any(term in lowered for term in config.SENSITIVE_TERMS)


def text_urgency(intent, text):
    lowered = text.lower()
    if has_sensitive_language(text):
        return "HIGH"
    if intent == "PAYMENT_ISSUE" and any(term in lowered for term in _DEBIT_TERMS):
        return "HIGH"

    level = _BASE.get(intent, "LOW")
    if any(term in lowered for term in config.URGENCY_UP_TERMS):
        level = _shift(level, +1)
    if any(term in lowered for term in config.URGENCY_DOWN_TERMS):
        level = _shift(level, -1)
    return level


def adjust_for_context(urgency, delivery=None, payment=None):
    """Raise urgency using order facts. Never lowers it."""
    if delivery and delivery.get("delayed") and delivery.get("delayed_days", 0) >= 5:
        urgency = max(urgency, "HIGH", key=config.URGENCY_LEVELS.index)
    if payment and payment.get("anomaly"):
        urgency = max(urgency, "HIGH", key=config.URGENCY_LEVELS.index)
    return urgency
