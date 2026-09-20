"""Mocked business data for the refund scenario. In-memory only — this is a
portfolio demo standing in for real order/billing APIs, not a database.

purchased_days_ago is a fixed int rather than a real date so eligibility
checks are deterministic and don't drift with wall-clock time.
"""

ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_id": "CUST-1",
        "amount": 49.99,
        "currency": "USD",
        "purchased_days_ago": 3,
        "status": "delivered",
        "refunded": False,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_id": "CUST-2",
        "amount": 1499.00,
        "currency": "USD",
        "purchased_days_ago": 2,
        "status": "delivered",
        "refunded": False,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_id": "CUST-1",
        "amount": 25.00,
        "currency": "USD",
        "purchased_days_ago": 20,
        "status": "delivered",
        "refunded": False,
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_id": "CUST-3",
        "amount": 60.00,
        "currency": "USD",
        "purchased_days_ago": 1,
        "status": "delivered",
        "refunded": True,
    },
}
