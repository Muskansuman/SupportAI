"""Decision engine: AUTO_RESOLVE, CLARIFICATION_REQUIRED or HUMAN_ESCALATION.

A deterministic, ordered rule set over the classifier's output and the facts
already gathered (order, eligibility). Urgency is not an input to the
escalation choice on purpose: urgency says how time-sensitive something is,
escalation says whether a person must take over. Every branch records a short
auditable reason, which the UI shows as "reasoning signals".
"""
from src.support import config
from src.support.urgency import has_sensitive_language

AUTO_RESOLVE = "AUTO_RESOLVE"
CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
HUMAN_ESCALATION = "HUMAN_ESCALATION"

_INTENT_LABELS = {
    "TRACK_ORDER": "tracking an order",
    "RETURN_REQUEST": "returning an item",
    "EXCHANGE_REQUEST": "exchanging an item",
    "REFUND_REQUEST": "a refund",
    "CANCEL_ORDER": "cancelling an order",
    "DELIVERY_ISSUE": "a delivery problem",
    "PAYMENT_ISSUE": "a payment problem",
    "DAMAGED_PRODUCT": "a damaged product",
    "WRONG_PRODUCT": "receiving the wrong product",
    "SIZE_ISSUE": "a size or fit problem",
    "HUMAN_AGENT": "talking to a person",
    "GENERAL_QUERY": "a general question",
}


def intent_label(intent):
    return _INTENT_LABELS.get(intent, intent.replace("_", " ").lower())


def _decision(action, outcome, reason, signals, clarification=None, escalation_reason=None):
    return {
        "action": action,
        "outcome": outcome,
        "reason": reason,
        "clarification": clarification,
        "escalation_reason": escalation_reason,
        "signals": signals,
    }


def _escalate(outcome, reason, signals):
    return _decision(HUMAN_ESCALATION, outcome, reason, signals, escalation_reason=reason)


def _clarify(outcome, reason, question, options, signals):
    return _decision(CLARIFICATION_REQUIRED, outcome, reason, signals, clarification={"question": question, "options": options})


def _order_options(candidate_orders):
    return [{"value": o["order_id"], "label": f"{o['product_name']} ({o['order_id']})"} for o in candidate_orders[:5]]


def decide(
    *,
    intent,
    confidence,
    text,
    order=None,
    evaluation=None,
    requested_size=None,
    order_id_not_found=None,
    candidate_orders=(),
    clarification_attempts=0,
):
    """Return the decision dict. `evaluation` is eligibility.evaluate_all(order, ...)."""
    signals = []
    band = config.confidence_band(confidence)
    already_asked = clarification_attempts >= config.MAX_CLARIFICATIONS_BEFORE_HANDOFF

    if intent == "HUMAN_AGENT":
        return _escalate("HUMAN_REQUESTED", "You requested to speak with a human agent", ["Customer explicitly requested human support", "Conversation context available for hand-off"])

    if has_sensitive_language(text):
        return _escalate("SENSITIVE_LANGUAGE", "Message contains sensitive or legal language", ["Sensitive language detected"])

    if band == "LOW":
        if already_asked:
            return _escalate("LOW_CONFIDENCE", "Still unclear after asking for clarification", ["Classification confidence is low", "Already asked one clarifying question"])
        return _clarify(
            "NEEDS_DETAIL",
            "Classification confidence is low",
            "I want to make sure I help with the right thing. What best describes the problem?",
            [{"value": "damaged", "label": "The item is damaged"}, {"value": "wrong_item", "label": "I got the wrong item"}, {"value": "size", "label": "The size or fit is wrong"}, {"value": "other", "label": "Something else"}],
            ["Classification confidence is low"],
        )

    if band == "MEDIUM" and not already_asked:
        return _clarify(
            "CONFIRM_INTENT",
            "Classification confidence is medium",
            f"Just to be sure, is this about {intent_label(intent)}?",
            [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No, something else"}],
            ["Classification confidence is medium"],
        )

    if intent in config.ORDER_DEPENDENT_INTENTS and order is None:
        if order_id_not_found:
            return _clarify(
                "ORDER_NOT_FOUND",
                f"Order {order_id_not_found} was not found",
                f"I couldn't find an order with the ID {order_id_not_found}. Could you check it, or pick one of your recent orders?",
                _order_options(candidate_orders),
                [f"Order ID {order_id_not_found} not found"],
            )
        return _clarify(
            "NEEDS_ORDER",
            "No order could be identified",
            "Which order is this about?",
            _order_options(candidate_orders),
            ["No order ID in the message", "No matching order context"],
        )

    if intent == "TRACK_ORDER":
        return _decision(AUTO_RESOLVE, "TRACKING_PROVIDED", "Order status retrieved", signals + ["Tracking data retrieved"])

    if intent == "DELIVERY_ISSUE":
        delivery = evaluation["delivery"]
        if delivery["state"] == "delivered":
            return _escalate("DELIVERED_BUT_NOT_RECEIVED", "Order is marked delivered but the customer says it did not arrive", signals + ["Order shows delivered", "Customer reports non-delivery"])
        if delivery["delayed"] and delivery["delayed_days"] >= 7:
            return _escalate("SHIPMENT_LOST_RISK", f"Shipment is {delivery['delayed_days']} days past its expected date", signals + [f"Shipment {delivery['delayed_days']} days late"])
        signals.append(f"Shipment {delivery['delayed_days']} days late" if delivery["delayed"] else "Shipment is on schedule")
        return _decision(AUTO_RESOLVE, "DELIVERY_STATUS_PROVIDED", "Delivery status retrieved", signals)

    if intent == "RETURN_REQUEST":
        result = evaluation["return"]
        signals.append("Return policy checked")
        if result["eligible"]:
            return _decision(AUTO_RESOLVE, "RETURN_APPROVED", "Order is eligible for return", signals + ["Order is return eligible"])
        return _decision(AUTO_RESOLVE, "RETURN_DENIED", f"Not eligible: {result['reason']}", signals + [f"Not return eligible ({result['reason']})"])

    if intent == "EXCHANGE_REQUEST":
        result = evaluation["exchange"]
        signals.append("Exchange policy checked")
        if result["eligible"] and not requested_size:
            sizes = result["details"]["replacement_sizes"]
            return _clarify("NEEDS_SIZE", "Exchange is possible but no size was requested", "Which size would you like instead?", [{"value": s, "label": s} for s in sizes], signals + ["Order is exchange eligible", "No requested size found"])
        if result["reason"] == "requested_size_unavailable":
            sizes = result["details"]["replacement_sizes"]
            return _clarify("SIZE_UNAVAILABLE", f"Size {requested_size} is not in stock", f"Size {requested_size} isn't available. These are: {', '.join(sizes)}. Which would you like?", [{"value": s, "label": s} for s in sizes], signals + [f"Requested size {requested_size} unavailable"])
        if result["eligible"]:
            return _decision(AUTO_RESOLVE, "EXCHANGE_APPROVED", "Order is eligible for exchange", signals + ["Order is exchange eligible", "Requested size available"])
        return _decision(AUTO_RESOLVE, "EXCHANGE_DENIED", f"Not eligible: {result['reason']}", signals + [f"Not exchange eligible ({result['reason']})"])

    if intent == "REFUND_REQUEST":
        result = evaluation["refund"]
        signals.append("Refund policy checked")
        if result["reason"] == "refund_due":
            status = result["details"]["refund_status"]
            if status == "overdue":
                return _escalate("REFUND_OVERDUE", "Refund is past the promised timeline", signals + ["Refund is overdue"])
            return _decision(AUTO_RESOLVE, "REFUND_IN_PROGRESS", "A refund is already on its way", signals + [f"Refund {status.replace('_', ' ')}"])
        if result["reason"] == "refund_after_return":
            return _decision(AUTO_RESOLVE, "REFUND_AFTER_RETURN", "Refund is issued once the return is received", signals + ["Return must be completed first"])
        return _decision(AUTO_RESOLVE, "REFUND_NOT_AVAILABLE", f"No refund available: {result['reason']}", signals + [f"No refund path ({result['reason']})"])

    if intent == "CANCEL_ORDER":
        result = evaluation["cancellation"]
        signals.append("Cancellation policy checked")
        if result["eligible"]:
            return _decision(AUTO_RESOLVE, "CANCELLATION_APPROVED", "Order has not shipped yet", signals + ["Order not yet shipped"])
        return _decision(AUTO_RESOLVE, "CANCELLATION_DENIED", f"Cannot cancel: {result['reason']}", signals + [f"Cannot cancel ({result['reason']})"])

    if intent == "PAYMENT_ISSUE":
        payment = evaluation["payment"]
        signals.append("Payment record checked")
        if payment["anomaly"] and payment["overdue"]:
            return _escalate("PAYMENT_DISPUTE", "Money was debited and the refund is overdue", signals + ["Amount debited for a cancelled order", "Refund is overdue"])
        if payment["anomaly"]:
            return _decision(AUTO_RESOLVE, "PAYMENT_REFUND_IN_PROGRESS", "Refund for the debited amount is in progress", signals + ["Amount debited for a cancelled order", "Refund within promised timeline"])
        return _escalate("PAYMENT_UNVERIFIED", "The reported charge could not be verified on this order", signals + ["No payment anomaly found on this order"])

    if intent in ("DAMAGED_PRODUCT", "WRONG_PRODUCT"):
        result = evaluation["report"]
        signals.append("Damaged/wrong item policy checked")
        if result["eligible"]:
            outcome = "DAMAGED_PICKUP_OFFERED" if intent == "DAMAGED_PRODUCT" else "WRONG_ITEM_PICKUP_OFFERED"
            return _decision(AUTO_RESOLVE, outcome, "Reported within the allowed window", signals + ["Reported within the allowed window"])
        return _escalate("POLICY_EXCEPTION", "Outside the reporting window and needs a policy exception", signals + [f"Cannot auto-approve ({result['reason']})"])

    if intent == "SIZE_ISSUE":
        return _decision(AUTO_RESOLVE, "SIZE_GUIDANCE", "Size guidance provided", signals + ["Size guide retrieved"])

    return _decision(AUTO_RESOLVE, "GENERAL_ANSWER", "General question answered from the help center", signals)
