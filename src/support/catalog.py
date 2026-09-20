"""Product browsing over the synthetic catalogue: search, filters, facets.

Read-only and deterministic. "Popular" ranks by how many orders in the
dataset contain the product, the only popularity signal that exists here
(there are no ratings or reviews).
"""
import re
from collections import Counter

SORTS = ("relevance", "popular", "price_asc", "price_desc", "discount")

# Everyday words shoppers use that the catalogue spells differently.
SYNONYMS = {
    "shoe": ["sneaker", "shoe"],
    "tee": ["t-shirt"],
    "tshirt": ["t-shirt"],
    "pant": ["trouser"],
    "jean": ["jean"],
    "top": ["top"],
    "sweatshirt": ["hoodie"],
    "coat": ["jacket"],
    "footwear": ["sneaker", "shoe"],
}

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _stem(token):
    for suffix in ("es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _words(text):
    return _WORD.findall(text.lower())


def _compact(p, popularity):
    return {
        "product_id": p["product_id"],
        "name": p["name"],
        "brand": p["brand"],
        "category": p["category"],
        "gender": p["gender"],
        "color": p["color"],
        "mrp": p["mrp"],
        "price": p["price"],
        "discount_pct": p["discount_pct"],
        "sizes": p["sizes"],
        "in_stock_sizes": [s for s in p["sizes"] if p["stock_by_size"].get(s, 0) > 0],
        "returnable": p["returnable"],
        "exchangeable": p["exchangeable"],
        "orders": popularity.get(p["product_id"], 0),
    }


class Catalog:
    def __init__(self, store):
        self.products = list(store.products.values())
        self.popularity = Counter(o["product_id"] for o in store.orders.values())
        self._index = {p["product_id"]: _words(f"{p['name']} {p['brand']} {p['category']} {p['gender']} {p['color']} {p.get('singular', '')}") for p in self.products}

    def _matches_query(self, product_id, tokens):
        words = self._index[product_id]
        for token in tokens:
            alternatives = SYNONYMS.get(_stem(token), [token])
            if not any(any(w.startswith(_stem(alt)) for w in words) for alt in alternatives):
                return False
        return True

    def search(self, q=None, gender=None, category=None, brand=None, color=None, size=None, min_price=None, max_price=None, sort="relevance", limit=24, offset=0):
        tokens = _words(q) if q else []
        items = []
        for p in self.products:
            if tokens and not self._matches_query(p["product_id"], tokens):
                continue
            if gender and p["gender"].lower() != gender.lower() and p["gender"] != "Unisex":
                continue
            if category and p["category"].lower() not in {c.lower() for c in category}:
                continue
            if brand and p["brand"].lower() not in {b.lower() for b in brand}:
                continue
            if color and p["color"].lower() not in {c.lower() for c in color}:
                continue
            if size and not any(p["stock_by_size"].get(s, 0) > 0 for s in size):
                continue
            if min_price is not None and p["price"] < min_price:
                continue
            if max_price is not None and p["price"] > max_price:
                continue
            items.append(p)

        pop = self.popularity
        if sort == "price_asc":
            items.sort(key=lambda p: (p["price"], p["product_id"]))
        elif sort == "price_desc":
            items.sort(key=lambda p: (-p["price"], p["product_id"]))
        elif sort == "discount":
            items.sort(key=lambda p: (-p["discount_pct"], p["product_id"]))
        else:  # popular, and the default order for relevance
            items.sort(key=lambda p: (-pop.get(p["product_id"], 0), p["product_id"]))

        page = items[offset : offset + limit]
        return {"total": len(items), "items": [_compact(p, pop) for p in page]}

    def facets(self):
        def counted(field):
            return [{"value": v, "count": n} for v, n in sorted(Counter(p[field] for p in self.products).items())]

        prices = [p["price"] for p in self.products]
        sizes = Counter(s for p in self.products for s in p["sizes"])
        return {
            "genders": counted("gender"),
            "categories": counted("category"),
            "brands": counted("brand"),
            "colors": counted("color"),
            "sizes": [{"value": s, "count": n} for s, n in sizes.items()],
            "price": {"min": min(prices), "max": max(prices)},
            "total": len(self.products),
        }
