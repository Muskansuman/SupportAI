"""Entity extraction: plain regexes over the customer message.

Identifiers and sizes are exactly the things a regex does better than a
language model (deterministic, auditable), so the LLM isn't asked to guess
them. Returns only what is actually present in the text.
"""
import re

_ORDER_FULL = re.compile(r"\bMYN[-\s]?DEMO[-\s]?(\d{4,6})\b", re.I)
_ORDER_BARE = re.compile(r"\border\s*(?:no\.?|number|id|#)?\s*[:#]?\s*(\d{4,6})\b", re.I)
_PRODUCT = re.compile(r"\bPRD[-\s]?DEMO[-\s]?(\d{3,5})\b", re.I)
_CUSTOMER = re.compile(r"\bCUST[-\s]?DEMO[-\s]?(\d{3,5})\b", re.I)

_SIZE_WORDS = {"small": "S", "medium": "M", "large": "L", "extra large": "XL", "extra-large": "XL", "xx large": "XXL"}
_LETTER_SIZE = r"(xxxl|xxl|xl|xs|s|m|l)"
_ANY_SIZE = r"(xxxl|xxl|xl|xs|s|m|l|\d{1,2})"
# Bare numbers ("for 2 days") are only a size when the word "size" is attached.
_SIZE_PATTERNS = [
    re.compile(rf"\bsize\s*(?:to|of|:|-)?\s*{_ANY_SIZE}\b", re.I),
    re.compile(rf"\b(?:to|in|for|into)\s+(?:a\s+)?{_LETTER_SIZE}\b(?:\s+size)?", re.I),
    re.compile(rf"\b{_ANY_SIZE}\s+size\b", re.I),
]

_ISSUE_KEYWORDS = {
    "damaged": ("damaged", "torn", "broken", "defective", "ripped", "stained", "faulty"),
    "wrong_item": ("wrong item", "wrong product", "different product", "different item", "not what i ordered", "someone else's"),
    "late": ("not arrived", "hasn't arrived", "hasnt arrived", "delayed", "not received", "still waiting"),
    "size_fit": ("too tight", "too loose", "doesn't fit", "doesnt fit", "too small", "too big", "wrong size", "size issue"),
    "payment": ("charged", "deducted", "debited", "payment failed", "paid twice"),
}

_ACTION_KEYWORDS = {
    "exchange": ("exchange", "swap", "replace"),
    "return": ("return", "send back", "pick up", "pickup"),
    "refund": ("refund", "money back"),
    "cancel": ("cancel",),
    "track": ("where is", "track", "status"),
}


def _normalise_order_id(digits):
    return f"MYN-DEMO-{int(digits):06d}"


def extract_entities(text):
    entities = {}

    match = _ORDER_FULL.search(text) or _ORDER_BARE.search(text)
    if match:
        entities["order_id"] = _normalise_order_id(match.group(1))

    match = _PRODUCT.search(text)
    if match:
        entities["product_id"] = f"PRD-DEMO-{int(match.group(1)):04d}"

    match = _CUSTOMER.search(text)
    if match:
        entities["customer_id"] = f"CUST-DEMO-{int(match.group(1)):05d}"

    lowered = text.lower()
    size = None
    for pattern in _SIZE_PATTERNS:
        found = pattern.search(text)
        if found:
            size = found.group(1).upper()
            break
    if size is None:
        for word, code in _SIZE_WORDS.items():
            if re.search(rf"\b{word}\b", lowered):
                size = code
                break
    if size:
        entities["requested_size"] = size

    for issue, terms in _ISSUE_KEYWORDS.items():
        if any(term in lowered for term in terms):
            entities["issue_type"] = issue
            break

    for action, terms in _ACTION_KEYWORDS.items():
        if any(term in lowered for term in terms):
            entities["requested_action"] = action
            break

    return entities
