export const STEP_ORDER = [
  { key: "understand", label: "Understanding request" },
  { key: "intent", label: "Detecting intent" },
  { key: "confidence", label: "Evaluating confidence" },
  { key: "urgency", label: "Evaluating urgency" },
  { key: "order", label: "Fetching order details" },
  { key: "eligibility", label: "Checking eligibility" },
  { key: "decision", label: "Deciding next step" },
  { key: "knowledge", label: "Searching knowledge base" },
  { key: "response", label: "Generating response" },
];

export const ACTION_LABELS = {
  AUTO_RESOLVE: "Auto resolve",
  CLARIFICATION_REQUIRED: "Needs clarification",
  HUMAN_ESCALATION: "Human escalation",
};

export const INTENT_LABELS = {
  TRACK_ORDER: "Track order",
  RETURN_REQUEST: "Return request",
  EXCHANGE_REQUEST: "Exchange request",
  REFUND_REQUEST: "Refund request",
  CANCEL_ORDER: "Cancel order",
  DELIVERY_ISSUE: "Delivery issue",
  PAYMENT_ISSUE: "Payment issue",
  DAMAGED_PRODUCT: "Damaged product",
  WRONG_PRODUCT: "Wrong product",
  SIZE_ISSUE: "Size or fit issue",
  HUMAN_AGENT: "Human agent",
  GENERAL_QUERY: "General query",
};

// Which eligibility result is the one a customer cares about for each intent.
export const RELEVANT_ELIGIBILITY = {
  RETURN_REQUEST: ["return", "Return eligibility"],
  EXCHANGE_REQUEST: ["exchange", "Exchange eligibility"],
  CANCEL_ORDER: ["cancellation", "Cancellation eligibility"],
  REFUND_REQUEST: ["refund", "Refund eligibility"],
  DAMAGED_PRODUCT: ["report", "Report eligibility"],
  WRONG_PRODUCT: ["report", "Report eligibility"],
};

export const money = (n) => `₹${Number(n).toLocaleString("en-IN")}`;

export function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function formatTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

export const humanize = (value) => (value ? value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : value);

export const percent = (x) => `${Math.round(x * 100)}%`;

export function makeId() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
