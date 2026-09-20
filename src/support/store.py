"""Read-only repository over the synthetic dataset.

Orders live behind this lookup layer (loaded once at startup, indexed by ID)
instead of in the vector store or the prompt: exact facts come from exact
lookups, and only the small slice a request needs is ever passed on.
"""
import json
import os
from pathlib import Path

from src.config import ROOT_DIR

DATA_DIR = Path(os.environ.get("SUPPORTAI_DATA_DIR", ROOT_DIR / "data" / "synthetic"))


class DataStore:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = Path(data_dir)
        if not (self.data_dir / "orders.json").exists():
            raise RuntimeError(f"Synthetic dataset not found in {self.data_dir}. Run `python scripts/generate_dataset.py` first.")

        self.meta = json.loads((self.data_dir / "meta.json").read_text())
        self.products = {p["product_id"]: p for p in self._load("products")}
        self.customers = {c["customer_id"]: c for c in self._load("customers")}
        self.orders = {o["order_id"]: o for o in self._load("orders")}
        self._by_customer = {}
        for order in self.orders.values():
            self._by_customer.setdefault(order["customer_id"], []).append(order)
        for orders in self._by_customer.values():
            orders.sort(key=lambda o: o["order_date"], reverse=True)

    def _load(self, name):
        return json.loads((self.data_dir / f"{name}.json").read_text())

    @property
    def demo_customer_id(self):
        return self.meta["demo_customer_id"]

    def get_order(self, order_id):
        return self.orders.get(order_id)

    def get_product(self, product_id):
        return self.products.get(product_id)

    def get_customer(self, customer_id):
        return self.customers.get(customer_id)

    def customer_orders(self, customer_id):
        return self._by_customer.get(customer_id, [])

    def conversations(self):
        return self._load("support_conversations")
