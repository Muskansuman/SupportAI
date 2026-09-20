"""The support pipeline: message -> intent/confidence/urgency -> entities ->
order lookup -> eligibility -> decision -> knowledge retrieval -> response.

Everything in the returned dict comes from a real step: the classifier's
probabilities, dictionary lookups, the rule engine, and the passages the
vector search actually returned. Workflow durations are measured. The LLM only
writes the final wording, and only from the facts and excerpts it is handed;
if it is unavailable the deterministic templates in messages.py answer.
"""
import hashlib
import os
import time

from src.support import config, messages
from src.support.context import resolve_order
from src.support.summary import customer_summary
from src.support.decision import AUTO_RESOLVE, CLARIFICATION_REQUIRED, HUMAN_ESCALATION, decide, intent_label
from src.support.eligibility import evaluate_all
from src.support.entities import extract_entities
from src.support.urgency import adjust_for_context, text_urgency

DEMO_NOTICE = "Synthetic Demo Environment"
MIN_SOURCE_SCORE = float(os.environ.get("SUPPORTAI_MIN_SOURCE_SCORE", 0.25))
MAX_SOURCES = 3
SOURCE_SCORE_MARGIN = 0.10

# Decisions that don't depend on any order data: no lookup or retrieval needed.
_EARLY_OUTCOMES = {"HUMAN_REQUESTED", "SENSITIVE_LANGUAGE", "LOW_CONFIDENCE", "NEEDS_DETAIL", "CONFIRM_INTENT"}
# Clarifications that are just questions, so retrieval would add nothing.
_QUESTION_OUTCOMES = {"NEEDS_ORDER", "ORDER_NOT_FOUND", "NEEDS_SIZE", "SIZE_UNAVAILABLE"}

# What the customer picks when the assistant asks "what best describes the problem?"
DETAIL_OPTION_INTENTS = {"damaged": "DAMAGED_PRODUCT", "wrong_item": "WRONG_PRODUCT", "size": "SIZE_ISSUE", "other": "HUMAN_AGENT"}

_QUERY_HINT = {
    "TRACK_ORDER": "delivery tracking status",
    "RETURN_REQUEST": "return policy",
    "EXCHANGE_REQUEST": "exchange policy size",
    "REFUND_REQUEST": "refund policy timeline",
    "CANCEL_ORDER": "cancellation policy",
    "DELIVERY_ISSUE": "delivery delayed policy",
    "PAYMENT_ISSUE": "payment charged cancelled refund",
    "DAMAGED_PRODUCT": "damaged product policy",
    "WRONG_PRODUCT": "wrong product policy",
    "SIZE_ISSUE": "size and fit help",
    "HUMAN_AGENT": "human support handoff",
    "GENERAL_QUERY": "help",
}

_ACTION_PREFIX = {
    "RETURN_APPROVED": ("RETURN_REQUEST_CREATED", "RET"),
    "EXCHANGE_APPROVED": ("EXCHANGE_REQUEST_CREATED", "EXC"),
    "CANCELLATION_APPROVED": ("CANCELLATION_CREATED", "CAN"),
    "DAMAGED_PICKUP_OFFERED": ("PICKUP_REQUEST_CREATED", "PKP"),
    "WRONG_ITEM_PICKUP_OFFERED": ("PICKUP_REQUEST_CREATED", "PKP"),
}


# The LLM sometimes uses narrow no-break spaces and non-breaking hyphens, which
# render oddly and stop order IDs from being copied or searched.
_NORMALISE = {**dict.fromkeys(map(ord, "\u00a0\u2007\u2009\u200a\u202f"), " "), **dict.fromkeys(map(ord, "\u2010\u2011"), "-")}


class Trace:
    """Collects workflow steps; `on_step` (if given) is called as each one finishes."""

    def __init__(self, on_step=None):
        self.steps = []
        self.on_step = on_step

    def _add(self, step):
        self.steps.append(step)
        if self.on_step:
            self.on_step(step)

    def done(self, key, label, started, detail=""):
        self._add({"key": key, "label": label, "status": "done", "detail": detail, "duration_ms": round((time.perf_counter() - started) * 1000, 1)})

    def skipped(self, key, label, reason):
        self._add({"key": key, "label": label, "status": "skipped", "detail": reason, "duration_ms": 0})


def _reference(prefix, seed):
    return f"DEMO-{prefix}-{hashlib.sha1(seed.encode()).hexdigest()[:6].upper()}"


def _order_view(order, product):
    last = order["tracking_events"][-1] if order["tracking_events"] else None
    keys = ("order_id", "product_id", "product_name", "brand", "category", "size", "color", "price", "mrp", "order_date", "expected_delivery_date", "delivery_date", "cancelled_date", "status", "payment_method", "payment_status", "carrier", "tracking_id", "return_eligible", "exchange_eligible", "replacement_sizes")
    view = {k: order[k] for k in keys}
    view["last_tracking_event"] = last
    view["available_sizes"] = [{"size": s, "in_stock": product["stock_by_size"].get(s, 0) > 0, "current": s == order["size"]} for s in product["sizes"]]
    return view


def _facts(order, product, evaluation, decision, requested_size, demo_action):
    lines = []
    if order:
        lines.append(f"Order {order['order_id']}: {order['product_name']}, size {order['size']}, {messages.money(order['price'])}, status {order['status']}" + (f", delivered {messages.day(order['delivery_date'])}" if order["delivery_date"] else f", expected {messages.day(order['expected_delivery_date'])}"))
        for name in ("return", "exchange", "cancellation", "refund", "report"):
            part = evaluation[name]
            relevant = {"RETURN_REQUEST": "return", "EXCHANGE_REQUEST": "exchange", "CANCEL_ORDER": "cancellation", "REFUND_REQUEST": "refund", "DAMAGED_PRODUCT": "report", "WRONG_PRODUCT": "report"}
            if decision["intent"] in relevant and relevant[decision["intent"]] == name:
                lines.append(f"{name.title()} checks: " + "; ".join(f"{'PASS' if c['passed'] else 'FAIL'} {c['name']} ({c['detail']})" for c in part["checks"]))
        if decision["intent"] in ("PAYMENT_ISSUE",):
            p = evaluation["payment"]
            lines.append(f"Payment: debited={p['debited']}, refund status={p['refund_status']}, expected by {p['expected_by']}")
        if decision["intent"] in ("DELIVERY_ISSUE", "TRACK_ORDER"):
            d = evaluation["delivery"]
            lines.append(f"Delivery: state={d['state']}, delayed={d['delayed']} ({d['delayed_days']} days)")
        if requested_size:
            lines.append(f"Requested size: {requested_size}")
        if evaluation["exchange"]["details"].get("replacement_sizes") and decision["intent"] == "EXCHANGE_REQUEST":
            lines.append("Sizes in stock: " + ", ".join(evaluation["exchange"]["details"]["replacement_sizes"]))
    lines.append(f"Decision: {decision['action']} ({decision['outcome']}): {decision['reason']}")
    if demo_action:
        lines.append(f"Demo action recorded (simulated, no real request): {demo_action['reference']}")
    return "\n".join(f"- {line}" for line in lines)


_PROMPT = """You are SupportAI, the assistant of a fashion store in a synthetic demo.
Write the reply to the customer using ONLY the FACTS and POLICY EXCERPTS below.
Rules: 2 to 4 short sentences, warm and specific. No tables and no headings. Do not invent dates, prices, sizes or order details. Do not promise anything not in the facts. Do not mention emails, SMS, notifications, apps, phone numbers, links or any channel that is not stated in the facts or excerpts; if the customer needs more detail, say they can open the order's page under My Orders. If the decision is HUMAN_ESCALATION, say a human-support escalation has been prepared and why; never say a person is connected or will call. If a demo reference is listed, mention it and say it is a demo.

CUSTOMER MESSAGE: {message}

FACTS:
{facts}

POLICY EXCERPTS:
{policy}

Reply:"""


class SupportPipeline:
    def __init__(self, store, classifier, knowledge, llm=None):
        self.store, self.classifier, self.knowledge, self.llm = store, classifier, knowledge, llm

    def _write(self, message, decision, order, product, evaluation, requested_size, demo_action, sources):
        """LLM wording grounded in facts + retrieved policy; templates if it fails."""
        fallback = messages.render(decision, order, evaluation, requested_size, demo_action)
        if self.llm is None or not sources:
            return fallback, "template", None
        prompt = _PROMPT.format(message=message, facts=_facts(order, product, evaluation, decision, requested_size, demo_action), policy="\n\n".join(f"[{s['title']} - {s['section']}]\n{s['text']}" for s in sources))
        try:
            text = self.llm.invoke(prompt).content.translate(_NORMALISE).strip()
            if text:
                return text, "llm", None
        except Exception as exc:  # network, quota, malformed response: never break the conversation
            return fallback, "template", f"LLM unavailable ({type(exc).__name__}); used the built-in response"
        return fallback, "template", "LLM returned an empty reply; used the built-in response"

    def resolve(self, message, customer_id=None, order_id=None, selected_size=None, clarification_attempts=0, intent_override=None, on_step=None):
        started = time.perf_counter()
        trace, warnings = Trace(on_step), []
        customer_id = customer_id if customer_id in self.store.customers else self.store.demo_customer_id

        # 1. entities (regex; explicit UI choices win over anything parsed from text)
        t = time.perf_counter()
        entities = extract_entities(message)
        if order_id:
            entities["order_id"] = order_id
        if selected_size:
            entities["requested_size"] = selected_size.upper()
        found = []
        if entities.get("order_id"):
            found.append(f"order {entities['order_id']}")
        if entities.get("requested_size"):
            found.append(f"size {entities['requested_size']}")
        trace.done("understand", "Understanding request", t, "Found " + " and ".join(found) if found else "No order ID or size in the message")

        # 2. intent / confidence / urgency
        t = time.perf_counter()
        if intent_override in config.INTENTS:
            classification = {"intent": intent_override, "urgency": None, "confidence": 1.0, "raw": "", "urgency_confidence": 0.0}
            confidence_source = "customer_confirmed"
            trace.done("intent", "Detecting intent", t, f"{intent_override} (confirmed by the customer)")
        else:
            try:
                classification = self.classifier.classify(message)
            except Exception as exc:  # a model failure must degrade to a clarification, not an error
                warnings.append(f"Classifier failed ({type(exc).__name__}); asking the customer to clarify")
                classification = {"intent": None, "urgency": None, "confidence": 0.0, "urgency_confidence": 0.0, "raw": ""}
            confidence_source = "model_token_probability"
            trace.done("intent", "Detecting intent", t, classification["intent"] or "No valid intent produced")
        intent = classification["intent"] or "GENERAL_QUERY"
        confidence = classification["confidence"]
        band = config.confidence_band(confidence)
        t = time.perf_counter()
        trace.done("confidence", "Evaluating confidence", t, band.capitalize())

        t = time.perf_counter()
        urgency = classification["urgency"] or text_urgency(intent, message)
        trace.done("urgency", "Evaluating urgency", t, urgency.title())

        # 3. decisions that need no order data leave immediately
        early = decide(intent=intent, confidence=confidence, text=message, clarification_attempts=clarification_attempts)
        order = product = evaluation = None
        candidates, order_not_found = [], None
        sources = []
        requested_size = entities.get("requested_size")

        if early["outcome"] in _EARLY_OUTCOMES:
            decision = early
            trace.skipped("order", "Fetching order details", "Not needed for this request")
            trace.skipped("eligibility", "Checking eligibility", "Not needed for this request")
            t = time.perf_counter()
            trace.done("decision", "Deciding next step", t, decision["action"].replace("_", " ").title())
            trace.skipped("knowledge", "Searching knowledge base", "Not needed for this request")
        else:
            # 4. order lookup
            t = time.perf_counter()
            customer_orders = self.store.customer_orders(customer_id)
            if entities.get("order_id"):
                order = self.store.get_order(entities["order_id"])
                if order is not None and order["customer_id"] != customer_id:
                    order = None  # another customer's order is treated as not found
                if order is None:
                    order_not_found = entities["order_id"]
                    candidates = [o for o in customer_orders][:5]
                detail = f"Found {order['order_id']}" if order else f"Order {entities['order_id']} not found for this account"
            else:
                order, candidates = resolve_order(intent, message, customer_orders, self.store.products)
                detail = f"Used your recent order {order['order_id']}" if order else (f"{len(candidates)} orders could match" if candidates else "No order needed or found")
            trace.done("order", "Fetching order details", t, detail)

            # 5. eligibility
            t = time.perf_counter()
            if order:
                product = self.store.get_product(order["product_id"])
                evaluation = evaluate_all(order, product, requested_size)
                urgency = adjust_for_context(urgency, evaluation["delivery"], evaluation["payment"])
                trace.done("eligibility", "Checking eligibility", t, "Policy rules applied to this order")
            else:
                trace.skipped("eligibility", "Checking eligibility", "No order to check")

            # 6. decision
            t = time.perf_counter()
            decision = decide(
                intent=intent,
                confidence=confidence,
                text=message,
                order=order,
                evaluation=evaluation,
                requested_size=requested_size,
                order_id_not_found=order_not_found,
                candidate_orders=candidates,
                clarification_attempts=clarification_attempts,
            )
            trace.done("decision", "Deciding next step", t, decision["action"].replace("_", " ").title())

            # 7. knowledge retrieval (only when the answer will be grounded in it)
            t2 = time.perf_counter()
            if decision["outcome"] in _QUESTION_OUTCOMES:
                trace.skipped("knowledge", "Searching knowledge base", "Only a question is needed")
            else:
                try:
                    hits = self.knowledge.search(f"{_QUERY_HINT[intent]} {message}", k=6)
                    seen = set()
                    # Keep only passages close to the best match, so a weak third
                    # hit isn't listed as if it supported the answer.
                    cutoff = max(MIN_SOURCE_SCORE, (hits[0]["score"] if hits else 0) - SOURCE_SCORE_MARGIN)
                    for hit in hits:
                        if hit["doc_id"] in seen or hit["score"] < cutoff:
                            continue
                        seen.add(hit["doc_id"])
                        sources.append(hit)
                    sources = sources[:MAX_SOURCES]
                    trace.done("knowledge", "Searching knowledge base", t2, f"{len(sources)} policy passage(s) from {len({s['doc_id'] for s in sources})} document(s)" if sources else "No relevant passage found")
                except Exception as exc:
                    warnings.append(f"Knowledge search failed ({type(exc).__name__})")
                    trace.skipped("knowledge", "Searching knowledge base", "Search failed")

        # 8. demo action (simulated; nothing is written)
        demo_action = None
        if decision["outcome"] in _ACTION_PREFIX and order:
            action_type, prefix = _ACTION_PREFIX[decision["outcome"]]
            demo_action = {"type": action_type, "reference": _reference(prefix, order["order_id"] + decision["outcome"]), "note": "Simulated for the demo. No real request or data change."}
        elif decision["action"] == HUMAN_ESCALATION:
            demo_action = {"type": "ESCALATION_PREPARED", "reference": _reference("ESC", customer_id + message), "note": "Prepared for the demo. No real agent is connected."}

        # 9. response
        t = time.perf_counter()
        text, response_source, warning = self._write(message, {**decision, "intent": intent}, order, product, evaluation, requested_size, demo_action, sources if decision["action"] != CLARIFICATION_REQUIRED else [])
        if warning:
            warnings.append(warning)
        trace.done("response", "Generating response", t, "Written by the LLM from the retrieved policy" if response_source == "llm" else "Built-in response")

        # 10. assemble
        signals = []
        if entities.get("order_id"):
            signals.append("Order ID identified in the message" if not order_id else "Order chosen by the customer")
        elif order:
            signals.append("Order inferred from the customer's recent orders")
        signals.append(f"Intent {intent} confirmed by the customer" if confidence_source == "customer_confirmed" else f"Intent {intent} detected with {band.lower()} confidence")
        signals += [f"{s['title']} retrieved" for s in sources] if response_source == "llm" else []
        signals += decision["signals"]
        if order and evaluation and intent in ("RETURN_REQUEST", "EXCHANGE_REQUEST"):
            part = evaluation["return" if intent == "RETURN_REQUEST" else "exchange"]
            signals += [f"{'✓' if c['passed'] else '✗'} {c['name']}" for c in part["checks"]]

        if demo_action and demo_action["type"] == "ESCALATION_PREPARED":
            signals.append("Escalation reference generated")

        return {
            "message": text,
            "customer_summary": customer_summary(decision, order, evaluation, demo_action, requested_size),
            "response_source": response_source,
            "intent": intent,
            "intent_label": intent_label(intent),
            "confidence": round(confidence, 4),
            "confidence_band": band,
            "confidence_source": confidence_source,
            "urgency": urgency,
            "knowledge_grounded": response_source == "llm" and bool(sources),
            "sources": [{"id": s["doc_id"], "title": s["title"], "section": s["section"], "excerpt": s["excerpt"], "score": s["score"]} for s in sources],
            "entities": entities,
            "order": _order_view(order, product) if order else None,
            "eligibility": evaluation,
            "recommended_action": decision["action"],
            "outcome": decision["outcome"],
            "decision_reason": decision["reason"],
            "escalation_needed": decision["action"] == HUMAN_ESCALATION,
            "escalation_reason": decision["escalation_reason"],
            "clarification": decision["clarification"],
            "demo_action": demo_action,
            "reasoning_signals": signals,
            "workflow_steps": trace.steps,
            "warnings": warnings,
            "customer_id": customer_id,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "notice": DEMO_NOTICE,
        }
