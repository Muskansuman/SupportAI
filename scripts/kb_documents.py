"""Knowledge-base policy documents for the synthetic fashion store.

Numbers come from src/support/config.py, so the text the assistant retrieves
always matches the windows the eligibility engine actually enforces.
"""
from src.support import config as c

NOTICE = "> Synthetic demo policy written for a demonstration store. It is not the policy of any real company.\n"

KB_DOCUMENTS = {
    "return_policy.md": f"""# Return Policy

{NOTICE}
## Return window
Items can be returned within **{c.RETURN_WINDOW_DAYS} days of delivery**. The window is counted from the delivery date shown on the order, not the order date.

## What can be returned
Unworn items with tags and original packaging attached. Innerwear, socks and other hygiene-sensitive items **cannot be returned** unless they arrive damaged or wrong (see the damaged product policy).

## How a return works
1. Open the order and choose "Return item", or ask the assistant.
2. A pickup is scheduled within 2 business days at the delivery address.
3. Once the item passes a quick quality check at the warehouse, the refund is started (see the refund policy).

## When a return is not possible
- The {c.RETURN_WINDOW_DAYS}-day window has passed.
- The item is in a non-returnable category.
- A return or exchange is already open on the order.
""",
    "exchange_policy.md": f"""# Exchange Policy

{NOTICE}
## Exchange window
Size exchanges are available within **{c.EXCHANGE_WINDOW_DAYS} days of delivery**, which is shorter than the return window.

## What can be exchanged
An item can be exchanged for a different **size of the same product and colour**, as long as that size is in stock. Innerwear and other non-returnable items are not exchangeable.

## How an exchange works
1. Choose the size you want from the sizes currently in stock.
2. A pickup for the original item and delivery of the new size are arranged together.
3. There is no extra charge for a size exchange.

## If your size is out of stock
Only sizes currently in stock are offered. If the size you need is unavailable, you can return the item for a refund instead, provided it is still within the return window.
""",
    "refund_policy.md": f"""# Refund Policy

{NOTICE}
## Refund timeline
Refunds are sent to the **original payment method within {c.REFUND_SLA_DAYS} days** of the refund being started. UPI and wallet refunds are usually faster than card or net-banking refunds.

## When a refund starts
- **Returned items:** after the item is received and passes the quality check.
- **Cancelled orders:** one day after the cancellation, for orders that were already paid.
- **Cash on delivery:** refunded to a bank account or wallet you provide, after the return is received.

## Refund not received
If a refund has not arrived after {c.REFUND_SLA_DAYS} days, it is treated as overdue and passed to a support agent to investigate with the payment provider.

## What is not refunded
Delivery charges on prepaid orders are refunded only when the cancellation or return was caused by us (damaged or wrong item).
""",
    "cancellation_policy.md": f"""# Cancellation Policy

{NOTICE}
## When you can cancel
An order can be cancelled **until it ships**. That covers the statuses placed, confirmed and packed.

## After shipping
Once an order has shipped it cannot be cancelled. You can refuse the delivery or, after it arrives, return it under the return policy ({c.RETURN_WINDOW_DAYS} days from delivery).

## What happens after a cancellation
- Prepaid orders are refunded to the original payment method within {c.REFUND_SLA_DAYS} days.
- Cash on delivery orders have nothing to refund because nothing was charged.
- Stock is released immediately.
""",
    "delivery_policy.md": """# Delivery Policy

> Synthetic demo policy written for a demonstration store. It is not the policy of any real company.

## Delivery estimates
Most orders arrive in 3 to 7 days. The expected delivery date is shown on the order and updated at each tracking step.

## Tracking
Every shipped order has a tracking ID and a list of tracking events. The status moves through placed, confirmed, packed, shipped, out for delivery and delivered.

## Delayed deliveries
If an order is past its expected date, the assistant shows how many days late it is. Shipments **more than 7 days late** are treated as possibly lost and passed to a support agent to investigate with the courier.

## Marked delivered but not received
If tracking says delivered but you did not receive the parcel, an agent reviews the courier's delivery proof and contacts you.
""",
    "payment_issue_policy.md": f"""# Payment Issue Policy

{NOTICE}
## Charged but the order failed or was cancelled
If money was debited but the order was cancelled or did not go through, the amount is refunded automatically to the original payment method within **{c.REFUND_SLA_DAYS} days**.

## Refund overdue
If the {c.REFUND_SLA_DAYS} days have passed and the money has not been returned, the case is escalated to a support agent as a **payment dispute**. An agent contacts the payment provider and updates you.

## Duplicate charges
A duplicate charge for the same order is refunded within {c.REFUND_SLA_DAYS} days once it is confirmed.

## Cash on delivery
Cash on delivery orders are not charged in advance, so payment problems normally do not apply.
""",
    "damaged_product_policy.md": f"""# Damaged Product Policy

{NOTICE}
## Reporting window
A damaged or defective item must be reported within **{c.REPORT_WINDOW_DAYS} days of delivery**.

## What we arrange
- A free pickup of the damaged item.
- A choice of a replacement (if in stock) or a full refund, including delivery charges.

## Evidence
Photos of the damage and the packaging help us process the claim faster. They are required for items that arrive with minor defects.

## Outside the reporting window
Claims made after {c.REPORT_WINDOW_DAYS} days need a policy exception and are reviewed by a support agent.
""",
    "wrong_product_policy.md": f"""# Wrong Product Policy

{NOTICE}
## If you received the wrong item
This covers a different product, colour or size from the one that was ordered. Report it within **{c.REPORT_WINDOW_DAYS} days of delivery**.

## What we arrange
- A free pickup of the wrong item.
- Delivery of the correct item if it is in stock, otherwise a full refund.

## Wrong size versus wrong product
If the size on the label matches what you ordered but it does not fit, that is a size exchange, not a wrong product. See the exchange policy.

## Outside the reporting window
Reports after {c.REPORT_WINDOW_DAYS} days need a policy exception and are reviewed by a support agent.
""",
    "size_help.md": """# Size and Fit Help

> Synthetic demo policy written for a demonstration store. It is not the policy of any real company.

## Choosing a size
Each product page lists a size chart in centimetres. Measure your chest, waist or foot length and compare it with the chart. If you are between two sizes, choose the larger for a relaxed fit.

## Apparel sizes
Tops and dresses run S, M, L, XL and XXL. Jeans and trousers use waist sizes in inches.

## Footwear sizes
Footwear uses UK sizes. If your foot is between sizes, go one size up.

## Fit differs by product
Slim fit runs closer to the body than regular fit. The fit type is shown on each product.

## If it doesn't fit
Within the exchange window you can swap the item for another size that is in stock. See the exchange policy.
""",
    "human_handoff_policy.md": """# Human Support Handoff Policy

> Synthetic demo policy written for a demonstration store. It is not the policy of any real company.

## When a person takes over
A support agent takes over when:
- you ask for a human agent
- the assistant is not confident about what you need, even after a clarifying question
- money is involved in a dispute, such as an overdue refund or a charge that cannot be verified
- the request needs a policy exception
- the message mentions legal action, fraud or a chargeback

## Hours
Human agents are available from 9 am to 9 pm IST, every day. Requests outside these hours are queued and answered the next morning.

## What is shared with the agent
The agent receives your conversation, the order details and the assistant's checks, so you do not need to repeat yourself.
""",
}
