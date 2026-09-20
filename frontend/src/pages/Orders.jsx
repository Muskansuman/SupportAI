import { useEffect, useState } from "react";
import { Package } from "lucide-react";
import { getCustomerOrders } from "../api";
import ProductImage from "../shop/ProductImage";
import { EmptyState, ErrorBox } from "../shop/States";
import { formatDate, humanize, money } from "../utils";

export const STATUS_TONE = { delivered: "good", out_for_delivery: "info", shipped: "info", placed: "info", confirmed: "info", packed: "info", cancelled: "bad", returned: "muted", return_initiated: "warn", exchange_initiated: "warn" };
const TABS = [
  ["all", "All", () => true],
  ["delivered", "Delivered", (o) => o.status === "delivered"],
  ["transit", "In transit", (o) => ["placed", "confirmed", "packed", "shipped", "out_for_delivery"].includes(o.status)],
  ["cancelled", "Cancelled", (o) => o.status === "cancelled"],
  ["returned", "Returned", (o) => ["returned", "return_initiated", "exchange_initiated"].includes(o.status)],
];

export const supportLink = (orderId, topic) => `#/support?order=${orderId}${topic ? `&topic=${topic}` : ""}`;

export default function Orders({ customerId }) {
  const [tab, setTab] = useState("all");
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!customerId) return;
    let cancelled = false;
    setState({ loading: true });
    getCustomerOrders(customerId, 200)
      .then((orders) => !cancelled && setState({ orders }))
      .catch((e) => !cancelled && setState({ error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [customerId, attempt]);

  const filter = TABS.find((t) => t[0] === tab)[2];
  const orders = (state.orders ?? []).filter(filter);
  const count = (fn) => (state.orders ?? []).filter(fn).length;

  return (
    <div className="page orders-page">
      <div className="listing-head">
        <div>
          <h1>My orders</h1>
          <p>Synthetic orders for the demo customer</p>
        </div>
      </div>

      <div className="tab-row" role="tablist">
        {TABS.map(([key, label, fn]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={`order-tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>
            {label} {state.orders && <span>{count(fn)}</span>}
          </button>
        ))}
      </div>

      {!customerId && <div className="state-box"><p>Connecting…</p></div>}
      {state.loading && customerId && <div className="skeleton order-skeleton" aria-busy="true" />}
      {state.error && <ErrorBox message={state.error} onRetry={() => setAttempt((n) => n + 1)} />}
      {state.orders && orders.length === 0 && (
        <EmptyState icon={Package} title={tab === "all" ? "You don't have any orders yet" : "No orders here"} text={tab === "all" ? "Orders you place will appear here." : "Nothing matches this tab."} action={<a className="btn-solid" href="#/shop">Start shopping</a>} />
      )}

      <ul className="order-list">
        {orders.map((o) => (
          <li key={o.order_id} className="order-row">
            <a className="order-thumb-lg" href={`#/orders/${o.order_id}`}>
              <ProductImage product={{ name: o.product_name, color: o.color, category: o.category }} />
            </a>
            <div className="order-row-main">
              <div className="order-row-top">
                <div>
                  <div className="product-brand">{o.brand}</div>
                  <a className="order-row-name" href={`#/orders/${o.order_id}`}>
                    {o.product_name.replace(o.brand, "").trim()}
                  </a>
                </div>
                <span className={`status-chip tone-${STATUS_TONE[o.status] ?? "muted"}`}>{humanize(o.status)}</span>
              </div>
              <dl className="order-row-facts">
                <div><dt>Order ID</dt><dd>{o.order_id}</dd></div>
                <div><dt>Ordered</dt><dd>{formatDate(o.order_date)}</dd></div>
                <div><dt>Size</dt><dd>{o.size}</dd></div>
                <div><dt>Amount</dt><dd>{money(o.price)}</dd></div>
              </dl>
              <div className="order-row-actions">
                {o.actions.track && <a className="btn-outline sm" href={`#/orders/${o.order_id}`}>Track order</a>}
                {o.actions.cancel && <a className="btn-outline sm" href={supportLink(o.order_id, "cancel")}>Cancel</a>}
                {o.actions.return && <a className="btn-outline sm" href={supportLink(o.order_id, "return")}>Return</a>}
                {o.actions.exchange && <a className="btn-outline sm" href={supportLink(o.order_id, "exchange")}>Exchange</a>}
                <a className="btn-solid sm" href={supportLink(o.order_id)}>Get help</a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
