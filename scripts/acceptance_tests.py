"""Acceptance tests for the support pipeline.

    python scripts/acceptance_tests.py                       # in-process (loads the model)
    python scripts/acceptance_tests.py --url http://localhost:8000   # against a running server

Runs the six scenarios from the spec plus edge cases through the same code
path the UI uses, and exits non-zero if any assertion fails.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results = []


def test(name, response, **checks):
    failed = [label for label, ok in checks.items() if not ok]
    results.append((name, failed))
    print(f"{'PASS' if not failed else 'FAIL'}  {name}")
    print(f"      intent={response['intent']} conf={response['confidence']:.0%} ({response['confidence_band']}) urgency={response['urgency']} action={response['recommended_action']} outcome={response['outcome']} grounded={response['knowledge_grounded']} sources={[s['id'] for s in response['sources']]}")
    print(f"      reply: {response['message'][:170]}")
    for label in failed:
        print(f"      ✗ {label}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    args = parser.parse_args()

    if args.url:
        def resolve(message, **kw):
            request = urllib.request.Request(f"{args.url}/support/resolve", data=json.dumps({"message": message, **kw}).encode(), headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(request, timeout=90).read())
    else:
        from src.support.service import build_pipeline

        pipeline = build_pipeline()
        resolve = pipeline.resolve

    steps = lambda r: {s["key"]: s["status"] for s in r["workflow_steps"]}  # noqa: E731

    r = resolve("I want to exchange my order MYN-DEMO-004281 for size L.")
    test("1. Exchange with order ID and size", r,
         intent_is_exchange=r["intent"] == "EXCHANGE_REQUEST",
         order_retrieved=r["order"] and r["order"]["order_id"] == "MYN-DEMO-004281",
         exchange_policy_retrieved=any(s["id"] == "exchange_policy" for s in r["sources"]),
         eligibility_checked=r["eligibility"]["exchange"]["eligible"] is True,
         replacement_sizes_shown=r["order"] and "L" in r["order"]["replacement_sizes"],
         decision_generated=r["recommended_action"] == "AUTO_RESOLVE" and r["outcome"] == "EXCHANGE_APPROVED",
         requested_size_extracted=r["entities"].get("requested_size") == "L",
         workflow_recorded=steps(r).get("order") == "done" and steps(r).get("eligibility") == "done")

    r = resolve("Where is my order MYN-DEMO-004281?")
    test("2. Track order", r,
         intent_is_track=r["intent"] == "TRACK_ORDER",
         order_retrieved=r["order"] and r["order"]["order_id"] == "MYN-DEMO-004281",
         status_shown=r["order"]["status"] == "delivered" and r["order"]["last_tracking_event"] is not None,
         message_has_status="delivered" in r["message"].lower())

    r = resolve("I was charged but my order was cancelled.")
    test("3. Payment issue", r,
         intent_is_payment=r["intent"] == "PAYMENT_ISSUE",
         urgency_high=r["urgency"] == "HIGH",
         payment_policy_retrieved=any(s["id"] == "payment_issue_policy" for s in r["sources"]),
         cancelled_order_found=r["order"] and r["order"]["status"] == "cancelled",
         escalated=r["recommended_action"] == "HUMAN_ESCALATION" and r["escalation_needed"])

    r = resolve("I want to talk to a human.")
    test("4. Human agent", r,
         intent_is_human=r["intent"] == "HUMAN_AGENT",
         escalated=r["recommended_action"] == "HUMAN_ESCALATION",
         no_order_lookup=r["order"] is None and steps(r).get("order") == "skipped",
         no_retrieval=r["sources"] == [] and steps(r).get("knowledge") == "skipped",
         demo_escalation_created=r["demo_action"] and r["demo_action"]["type"] == "ESCALATION_PREPARED")

    r = resolve("My product isn't right.")
    test("5. Ambiguous message", r,
         lower_confidence=r["confidence"] < 0.85,
         clarification=r["recommended_action"] == "CLARIFICATION_REQUIRED",
         has_question=bool(r["clarification"] and r["clarification"]["question"]),
         not_escalated_yet=not r["escalation_needed"])
    ambiguous = r

    r = resolve("Can you help me?")
    test("6. General query", r,
         intent_is_general=r["intent"] == "GENERAL_QUERY",
         no_fabricated_order=r["order"] is None and "MYN-DEMO" not in r["message"],
         helpful_reply=len(r["message"]) > 30)

    # ---- edge cases
    r = resolve("I want to exchange order MYN-DEMO-004281 for size XXL")
    test("7. Requested size out of stock", r,
         size_unavailable=r["outcome"] == "SIZE_UNAVAILABLE",
         alternatives_offered={"S", "L", "XL"} <= {o["value"] for o in r["clarification"]["options"]})

    r = resolve("Where is my order MYN-DEMO-999999?")
    test("8. Order not found", r, not_found=r["outcome"] == "ORDER_NOT_FOUND", no_order=r["order"] is None)

    r = resolve("Where is my order MYN-DEMO-000001?", customer_id="CUST-DEMO-00042")
    test("9. Another customer's order is not exposed", r, not_found=r["outcome"] == "ORDER_NOT_FOUND", no_order=r["order"] is None)

    r = resolve("I want a refund for my order.")
    test("10. Several possible orders -> ask which", r, asks_which=r["outcome"] == "NEEDS_ORDER", offers_orders=len(r["clarification"]["options"]) >= 2)

    r = resolve("I want a refund for my order.", order_id="MYN-DEMO-004281")
    test("11. Choosing an order continues the request", r, resolved=r["order"] and r["order"]["order_id"] == "MYN-DEMO-004281", not_asking_again=r["outcome"] != "NEEDS_ORDER")

    r = resolve(ambiguous["message"] if False else "My product isn't right.", intent_override="DAMAGED_PRODUCT")
    test("12. Customer clarifies (damaged) -> resolved", r,
         confirmed_by_customer=r["confidence_source"] == "customer_confirmed",
         order_from_context=r["order"] and r["order"]["order_id"] == "MYN-DEMO-004281",
         pickup_offered=r["outcome"] == "DAMAGED_PICKUP_OFFERED")

    r = resolve("This is a scam, I will go to consumer court over my order MYN-DEMO-004281")
    test("13. Sensitive language always goes to a person", r, escalated=r["recommended_action"] == "HUMAN_ESCALATION" and r["outcome"] == "SENSITIVE_LANGUAGE")

    failed = [name for name, f in results if f]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
