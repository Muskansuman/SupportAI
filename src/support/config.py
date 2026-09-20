"""Configuration for the fashion e-commerce support demo.

Everything here is shared by the dataset generator and the runtime engines so
the labels in the data and the behavior of the pipeline cannot drift apart.
Thresholds can be overridden with SUPPORTAI_* environment variables.
"""
import os
from datetime import datetime

# Fixed demo clock. Return/exchange windows are measured against this, not
# wall-clock time, so the synthetic orders don't silently age out of
# eligibility while the demo is deployed.
DEMO_NOW = datetime(2026, 9, 20, 12, 0, 0)

INTENTS = (
    "TRACK_ORDER",
    "RETURN_REQUEST",
    "EXCHANGE_REQUEST",
    "REFUND_REQUEST",
    "CANCEL_ORDER",
    "DELIVERY_ISSUE",
    "PAYMENT_ISSUE",
    "DAMAGED_PRODUCT",
    "WRONG_PRODUCT",
    "SIZE_ISSUE",
    "HUMAN_AGENT",
    "GENERAL_QUERY",
)

# Intents that cannot be answered without knowing which order is meant.
ORDER_DEPENDENT_INTENTS = frozenset(
    {
        "TRACK_ORDER",
        "RETURN_REQUEST",
        "EXCHANGE_REQUEST",
        "REFUND_REQUEST",
        "CANCEL_ORDER",
        "DELIVERY_ISSUE",
        "PAYMENT_ISSUE",
        "DAMAGED_PRODUCT",
        "WRONG_PRODUCT",
    }
)

URGENCY_LEVELS = ("LOW", "MEDIUM", "HIGH")

# ---- policy windows (also written into the knowledge-base documents) ----
RETURN_WINDOW_DAYS = 14
EXCHANGE_WINDOW_DAYS = 10
REPORT_WINDOW_DAYS = 7  # damaged / wrong item must be reported within this
REFUND_SLA_DAYS = 7  # refunds reach the original payment method within this

CANCELLABLE_STATUSES = frozenset({"placed", "confirmed", "packed"})
IN_TRANSIT_STATUSES = frozenset({"shipped", "out_for_delivery"})

# ---- confidence bands ----
HIGH_CONFIDENCE = float(os.environ.get("SUPPORTAI_HIGH_CONFIDENCE", 0.85))
MEDIUM_CONFIDENCE = float(os.environ.get("SUPPORTAI_MEDIUM_CONFIDENCE", 0.60))

# How many times the assistant asks a clarifying question on a low/medium
# confidence message before handing the conversation to a human.
MAX_CLARIFICATIONS_BEFORE_HANDOFF = int(os.environ.get("SUPPORTAI_MAX_CLARIFICATIONS", 1))

# Language that always goes to a person regardless of intent or confidence.
SENSITIVE_TERMS = (
    "fraud",
    "scam",
    "cheated",
    "consumer court",
    "lawyer",
    "legal action",
    "police",
    "sue you",
    "chargeback",
)

URGENCY_UP_TERMS = ("urgent", "asap", "immediately", "right now", "emergency", "today itself")
URGENCY_DOWN_TERMS = ("no rush", "no hurry", "whenever", "not urgent", "when you get a chance")


def confidence_band(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "HIGH"
    if confidence >= MEDIUM_CONFIDENCE:
        return "MEDIUM"
    return "LOW"
