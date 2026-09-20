import { Check, Package, X } from "lucide-react";
import { RELEVANT_ELIGIBILITY, formatDate, humanize, money } from "../utils";

const STATUS_TONE = {
  delivered: "good",
  out_for_delivery: "info",
  shipped: "info",
  placed: "info",
  confirmed: "info",
  packed: "info",
  cancelled: "bad",
  returned: "muted",
  return_initiated: "warn",
  exchange_initiated: "warn",
};

// Return/exchange flags only mean something once the item has been delivered.
const AFTER_DELIVERY = new Set(["delivered", "return_initiated", "returned", "exchange_initiated"]);

function Flag({ ok, children }) {
  return (
    <span className={`flag ${ok ? "flag-yes" : "flag-no"}`}>
      {ok ? <Check size={13} /> : <X size={13} />} {children}
    </span>
  );
}

export default function OrderCard({ order, intent, eligibility, selectedSize, onSelectSize, disabled }) {
  const relevant = RELEVANT_ELIGIBILITY[intent];
  const part = relevant && eligibility ? eligibility[relevant[0]] : null;
  const showSizes = intent === "EXCHANGE_REQUEST" || intent === "SIZE_ISSUE";
  const discount = order.mrp > order.price ? Math.round((1 - order.price / order.mrp) * 100) : 0;

  return (
    <div className="order-card">
      <div className="order-card-top">
        <div className="order-thumb">
          <Package size={22} />
        </div>
        <div className="order-main">
          <div className="order-name">{order.product_name}</div>
          <div className="order-sub">
            {order.brand} · {order.category}
          </div>
          <div className="order-price">
            {money(order.price)}
            {discount > 0 && (
              <>
                <s>{money(order.mrp)}</s>
                <span className="order-discount">{discount}% off</span>
              </>
            )}
          </div>
        </div>
        <span className={`status-chip tone-${STATUS_TONE[order.status] ?? "muted"}`}>{humanize(order.status)}</span>
      </div>

      <dl className="order-facts">
        <div>
          <dt>Order</dt>
          <dd>{order.order_id}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{order.size}</dd>
        </div>
        <div>
          <dt>Color</dt>
          <dd>{order.color}</dd>
        </div>
        <div>
          <dt>{order.cancelled_date ? "Cancelled" : order.delivery_date ? "Delivered" : "Expected"}</dt>
          <dd>{formatDate(order.cancelled_date ?? order.delivery_date ?? order.expected_delivery_date)}</dd>
        </div>
        <div>
          <dt>Payment</dt>
          <dd>
            {order.payment_method} · {humanize(order.payment_status)}
          </dd>
        </div>
        <div>
          <dt>Ordered</dt>
          <dd>{formatDate(order.order_date)}</dd>
        </div>
      </dl>

      <div className="order-flags">
        {AFTER_DELIVERY.has(order.status) && (
          <>
            <Flag ok={order.return_eligible}>Return</Flag>
            <Flag ok={order.exchange_eligible}>Exchange</Flag>
          </>
        )}
        {order.last_tracking_event && (
          <span className="last-event">
            Last update: {humanize(order.last_tracking_event.status.toLowerCase())} · {formatDate(order.last_tracking_event.timestamp)}
          </span>
        )}
      </div>

      {part && (
        <div className="checks">
          <div className="checks-title">
            {relevant[1]}: <strong className={part.eligible ? "yes" : "no"}>{part.eligible ? "Eligible" : "Not eligible"}</strong>
          </div>
          <ul>
            {part.checks.map((c) => (
              <li key={c.name} className={c.passed ? "check-pass" : "check-fail"}>
                {c.passed ? <Check size={14} /> : <X size={14} />}
                <span>
                  {c.name}
                  <span className="check-detail"> · {c.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showSizes && order.available_sizes && (
        <div className="size-picker">
          <div className="size-title">{selectedSize ? `Selected size: ${selectedSize}` : "Choose a replacement size"}</div>
          <div className="size-row">
            {order.available_sizes.map((s) => {
              const unavailable = !s.in_stock || s.current;
              return (
                <button
                  key={s.size}
                  type="button"
                  className={`size-chip ${s.current ? "current" : ""} ${selectedSize === s.size ? "selected" : ""}`}
                  disabled={unavailable || disabled}
                  onClick={() => onSelectSize(s.size)}
                  title={s.current ? "Your current size" : s.in_stock ? "In stock" : "Out of stock"}
                >
                  {s.size}
                </button>
              );
            })}
          </div>
          <div className="size-legend">Greyed sizes are your current size or out of stock.</div>
        </div>
      )}
    </div>
  );
}
