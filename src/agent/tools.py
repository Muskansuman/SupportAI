"""Plain-function tools for the refund scenario. No framework, no tool-calling
library — the agent orchestration layer (src/agent/refund_agent.py) calls
these directly. Mocked business logic standing in for real order/refund APIs.
"""
from src.agent.mock_data import ORDERS


def get_order(order_id):
    """Look up an order by id. Returns the order dict, or None if not found."""
    return ORDERS.get(order_id)


def check_refund_eligibility(order, refund_window_days=7):
    """Returns (eligible: bool, reason: str)."""
    if order is None:
        return False, "order_not_found"
    if order["refunded"]:
        return False, "already_refunded"
    if order["purchased_days_ago"] > refund_window_days:
        return False, "refund_window_expired"
    return True, "eligible"


def create_refund_request(order):
    """Mocked action: 'submits' a refund and mutates the mock order record
    so repeated lookups correctly reflect it as already refunded.
    """
    order["refunded"] = True
    return {
        "refund_id": f"REF-{order['order_id']}",
        "status": "submitted",
        "amount": order["amount"],
        "currency": order["currency"],
    }
