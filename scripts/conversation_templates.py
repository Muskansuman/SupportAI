"""Customer-message templates for the synthetic support conversations.

Each intent has `with_id` templates (mention an order ID) and `no_id`
templates. The LAST `UNSEEN_PER_LIST` entries of every list are held out:
they are only used to build the `test_unseen` split, so evaluation on it
measures phrasing the classifier never saw, not memorised templates.

Slots: {oid} order ID, {size} requested size, {item} e.g. "black t-shirt".
"""

UNSEEN_PER_LIST = 2

TEMPLATES = {
    "TRACK_ORDER": {
        "with_id": [
            "Where is my order {oid}?",
            "Can you tell me the status of order {oid}?",
            "Track {oid} please",
            "What is the delivery status of {oid}",
            "Has {oid} been shipped yet?",
            "When will order {oid} reach me?",
            "Need an update on {oid}",
            "Could you let me know how far along {oid} is?",
            "I placed {oid} a few days back, where has it got to now",
        ],
        "no_id": [
            "Where is my order?",
            "Track my order",
            "What's the status of my order?",
            "When will my order arrive?",
            "Has my {item} been shipped?",
            "Can you update me on my latest order?",
            "Where has my parcel reached?",
            "Any news on my package?",
            "How much longer until my {item} gets here?",
        ],
    },
    "RETURN_REQUEST": {
        "with_id": [
            "I want to return order {oid}",
            "Please arrange a return for {oid}",
            "How do I return {oid}?",
            "Return request for order {oid}",
            "I'd like to send back the item from {oid}",
            "Can I return {oid}? I don't want it anymore",
            "Start a return for {oid}",
            "The {item} in {oid} isn't for me, I'd like to give it back",
            "Is it too late to return what I got in {oid}?",
        ],
        "no_id": [
            "I want to return my order",
            "How do I return an item?",
            "I'd like to return my recent order",
            "Please arrange a return pickup",
            "Can I return this {item}?",
            "I don't want my {item} anymore, want to send it back",
            "Return my last order",
            "Would it be possible to give back something I bought recently?",
            "I've changed my mind about the {item} and want to return it",
        ],
    },
    "EXCHANGE_REQUEST": {
        "with_id": [
            "I want to exchange order {oid} for size {size}",
            "Can I swap {oid} for a {size}?",
            "Exchange {oid} to size {size} please",
            "Need a different size for {oid}, size {size} please",
            "Please exchange the {item} from {oid} to {size}",
            "The size in {oid} doesn't fit, can I get {size}?",
            "Change the size of {oid} to {size}",
            "I want to exchange order {oid}",
            "Can I exchange {oid}?",
            "The one I got in {oid} is off, could you send me a {size} instead?",
            "Looking to trade {oid} for size {size}",
        ],
        "no_id": [
            "I received the wrong size and want to exchange it",
            "Can I exchange my {item} for a {size}?",
            "I want to exchange my order for size {size}",
            "How do I exchange for a different size?",
            "Need to swap my {item} for a bigger size",
            "Exchange my recent order to {size}",
            "This doesn't fit, I want size {size} instead",
            "Could I trade this in for a {size}?",
            "Can I get the same {item} in another size?",
        ],
    },
    "REFUND_REQUEST": {
        "with_id": [
            "Where is my refund for {oid}?",
            "I want a refund for order {oid}",
            "Refund status for {oid}",
            "Please refund {oid}",
            "When will I get my money back for {oid}?",
            "I returned {oid} but haven't got the refund",
            "Need refund on {oid}",
            "Any word on the money for {oid}?",
            "Still waiting to be reimbursed for {oid}",
        ],
        "no_id": [
            "I want a refund for my order",
            "Where is my refund?",
            "When will I get my money back?",
            "Please refund my order",
            "I haven't received my refund",
            "Refund status please",
            "I want my money back for the {item}",
            "Could you look into reimbursing me?",
            "How long until the refund lands in my account?",
        ],
    },
    "CANCEL_ORDER": {
        "with_id": [
            "Cancel order {oid}",
            "I want to cancel {oid}",
            "Please cancel my order {oid} before it ships",
            "Can {oid} be cancelled?",
            "Stop order {oid}, I don't need it",
            "Need to cancel {oid} right away",
            "Cancel {oid} please",
            "Would you be able to call off {oid}?",
            "I ordered {oid} by mistake, undo it",
        ],
        "no_id": [
            "I want to cancel my order",
            "Cancel my order please",
            "Can I still cancel my order?",
            "How do I cancel an order?",
            "I ordered the {item} by mistake, cancel it",
            "Please cancel my latest order",
            "Want to cancel what I just ordered",
            "Is it possible to call off my recent purchase?",
            "Changed my mind, please stop the {item} from shipping",
        ],
    },
    "DELIVERY_ISSUE": {
        "with_id": [
            "Order {oid} has not arrived yet",
            "{oid} is delayed, where is it",
            "My order {oid} hasn't been delivered",
            "It's been too long, {oid} still hasn't reached me",
            "Delivery of {oid} is late",
            "Why is {oid} taking so long?",
            "{oid} not received",
            "I was told {oid} would be here by now, it isn't",
            "Waiting ages for {oid} to show up",
        ],
        "no_id": [
            "My order hasn't arrived yet",
            "My package is late",
            "Order delayed, still not received",
            "Why is my delivery taking so long?",
            "I haven't received my order",
            "Delivery is delayed for my {item}",
            "It's past the delivery date and nothing has come",
            "The parcel was meant to be here already",
            "Still no sign of my {item}",
        ],
    },
    "PAYMENT_ISSUE": {
        "with_id": [
            "I was charged but order {oid} was cancelled",
            "Money deducted for {oid} but the order failed",
            "Payment debited for {oid}, order cancelled, where's my money",
            "Amount was deducted for order {oid} but I got nothing",
            "Charged twice for {oid}",
            "My payment for {oid} went through but the order shows cancelled",
            "Debited for {oid} yet no order confirmation",
            "The bank took the money for {oid} yet there's no order",
            "{oid} got cancelled but my account was still debited",
        ],
        "no_id": [
            "I was charged but my order was cancelled",
            "Money was deducted but my order didn't go through",
            "Payment failed but amount debited",
            "I paid twice for one order",
            "My card was charged but there is no order",
            "Amount deducted from my account but order not confirmed",
            "UPI payment deducted, order cancelled",
            "You took my money and cancelled the order",
            "Why did the bank debit me when the purchase fell through?",
        ],
    },
    "DAMAGED_PRODUCT": {
        "with_id": [
            "The product in {oid} arrived damaged",
            "Order {oid} is broken",
            "I received a torn {item} in {oid}",
            "{oid} came damaged, need a replacement",
            "My {item} from {oid} is defective",
            "There's a stain on the item in {oid}",
            "Damaged item received for {oid}",
            "Opened {oid} and found it ripped",
            "The {item} from {oid} has a hole in it",
        ],
        "no_id": [
            "My product arrived damaged",
            "I got a damaged item",
            "The {item} is torn",
            "The item I received is defective",
            "There is a hole in my {item}",
            "My order came broken",
            "The fabric has a stain on it",
            "It looks used and it's falling apart",
            "The stitching came undone as soon as I took it out of the bag",
        ],
    },
    "WRONG_PRODUCT": {
        "with_id": [
            "I received a different product for {oid}",
            "Wrong item delivered in {oid}",
            "{oid} has the wrong product inside",
            "The item in {oid} is not what I ordered",
            "Got someone else's order in {oid}",
            "This isn't the {item} I ordered in {oid}",
            "Wrong colour delivered for {oid}",
            "Not the thing I picked, what came in {oid} is completely different",
            "{oid} contained an item I never ordered",
        ],
        "no_id": [
            "I received a different product than what I ordered",
            "Wrong item delivered",
            "This isn't what I ordered",
            "I got the wrong product",
            "The colour is different from what I ordered",
            "You sent me the wrong item",
            "Received a different item",
            "What arrived looks nothing like my order",
            "This is a different thing altogether from what I bought",
        ],
    },
    "SIZE_ISSUE": {
        "with_id": [
            "Is the size in order {oid} true to size?",
            "The {item} from {oid} feels too small, is that normal?",
            "Which size should I have picked for {oid}?",
            "Does {oid} run small or large?",
            "I'm confused about the fit of {oid}",
            "Size guide for the item in {oid}?",
            "Any advice on the sizing of what came in {oid}?",
        ],
        "no_id": [
            "What size should I order?",
            "Does this run small?",
            "How do I find my size?",
            "I'm between M and L, which should I pick?",
            "Is the fit slim or regular?",
            "Do you have a size chart?",
            "Are your sizes true to fit?",
            "Which size would suit someone of my build?",
            "Do the jeans come up narrow?",
        ],
    },
    "HUMAN_AGENT": {
        "with_id": [
            "Connect me to an agent about {oid}",
            "I want to talk to someone regarding {oid}",
            "Get me a human for order {oid}",
            "Can a person look at {oid}?",
        ],
        "no_id": [
            "I want to talk to a human agent",
            "Connect me to a human",
            "Can I speak to a person?",
            "I need a real person to help me",
            "Transfer me to customer care",
            "Let me talk to your support team",
            "Human agent please",
            "Get me someone from your team, not a bot",
            "Is there a live person I can chat with?",
        ],
    },
    "GENERAL_QUERY": {
        "no_id": [
            "Can you help me?",
            "Hi",
            "Hello, I need some help",
            "What can you do?",
            "How does your store work?",
            "Do you deliver to my city?",
            "What payment methods do you accept?",
            "What are your support hours?",
            "Do you have gift cards?",
            "Are there any discounts going on?",
            "Just browsing, can you tell me what you handle?",
            "Do you ship internationally?",
        ],
    },
}

# Messages that don't say what is wrong. Their label is drawn at random from
# AMBIGUOUS_LABELS, so a model trained on them learns to spread probability
# across the plausible intents instead of being confidently wrong.
AMBIGUOUS = {
    "with_id": [
        "Something is wrong with order {oid}",
        "My product from {oid} isn't right",
        "Not happy with {oid}",
        "There's an issue with {oid}",
        "I have a problem with {oid}",
        "{oid} is not what I hoped for",
        "Order {oid} isn't as expected",
    ],
    "no_id": [
        "My product isn't right",
        "Something is wrong with my order",
        "I have a problem with my order",
        "This isn't good",
        "I'm not happy with what I got",
        "There's an issue with my item",
        "My {item} isn't right",
        "It's not working out",
        "Something's off about my purchase",
    ],
}

AMBIGUOUS_LABELS = {
    "DAMAGED_PRODUCT": 0.30,
    "WRONG_PRODUCT": 0.30,
    "SIZE_ISSUE": 0.20,
    "RETURN_REQUEST": 0.20,
}

INTENT_WEIGHTS = {
    "TRACK_ORDER": 14,
    "RETURN_REQUEST": 12,
    "EXCHANGE_REQUEST": 11,
    "REFUND_REQUEST": 10,
    "CANCEL_ORDER": 8,
    "DELIVERY_ISSUE": 9,
    "PAYMENT_ISSUE": 7,
    "DAMAGED_PRODUCT": 7,
    "WRONG_PRODUCT": 5,
    "SIZE_ISSUE": 5,
    "HUMAN_AGENT": 5,
    "GENERAL_QUERY": 7,
}

PREFIXES = ["", "", "", "", "hi, ", "hello, ", "hey team, ", "hi support, ", "good morning, ", "please help: ", "urgent: ", "excuse me, "]
SUFFIXES = ["", "", "", "", " please help", " thanks", " thank you", " kindly check", " asap", " no rush", " waiting for your reply"]

SENSITIVE_SUFFIXES = [
    ". This is a scam and I will go to consumer court",
    ". I feel cheated, I'm considering legal action",
    ". If this isn't fixed I'll file a chargeback",
    ". This looks like fraud",
]
