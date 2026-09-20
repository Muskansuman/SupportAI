import { useEffect, useState } from "react";
import { Check, LifeBuoy, PackageX, X } from "lucide-react";
import { getEligibility, getOrder, getTracking } from "../api";
import ProductImage from "../shop/ProductImage";
import { EmptyState, ErrorBox } from "../shop/States";
import Timeline from "../shop/Timeline";
import { formatDate, humanize, money } from "../utils";
import { STATUS_TONE, supportLink } from "./Orders";

function EligibilityRow({ label, part }) {
  return (
    <div className="elig-row">
      <div className="elig-head">
        <strong>{label}</strong>
        <span className={part.eligible ? "yes" : "no"}>{part.eligible ? "Eligible" : "Not eligible"}</span>
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
  );
}

export default function OrderDetail({ id, customerId, demoNow }) {
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!customerId) return;
    let cancelled = false;
    setState({ loading: true });
    Promise.all([getOrder(id, customerId), getTracking(id, customerId), getEligibility(id, customerId)])
      .then(([order, tracking, eligibility]) => !cancelled && setState({ order, tracking, eligibility }))
      .catch((e) => !cancelled && setState({ error: e.message, notFound: /not found/i.test(e.message) }));
    return () => {
      cancelled = true;
    };
  }, [id, customerId, attempt]);

  if (state.loading) return <div className="page"><div className="skeleton detail-skeleton" aria-busy="true" /></div>;
  if (state.notFound)
    return (
      <div className="page">
        <EmptyState icon={PackageX} title="Order not found" text={`We couldn't find order ${id} on your account.`} action={<a className="btn-outline" href="#/orders">Back to my orders</a>} />
      </div>
    );
  if (state.error) return <div className="page"><ErrorBox message={state.error} onRetry={() => setAttempt((n) => n + 1)} /></div>;

  const { order: o, tracking: t, eligibility: e } = state;
  const delivered = o.status === "delivered";
  const upcoming = ["placed", "confirmed", "packed", "shipped", "out_for_delivery"].includes(o.status);
  const late = upcoming && new Date(o.expected_delivery_date) < new Date(demoNow ?? "2026-09-20T12:00:00");

  return (
    <div className="page order-detail">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/orders">My orders</a> / {o.order_id}
      </nav>

      <div className="detail-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h1>Order #{o.order_id}</h1>
              <p>Placed {formatDate(o.order_date)}</p>
            </div>
            <span className={`status-chip tone-${STATUS_TONE[o.status] ?? "muted"}`}>{humanize(o.status)}</span>
          </div>

          <div className="order-product">
            <div className="order-thumb-lg">
              <ProductImage product={{ name: o.product_name, color: o.color, category: o.category }} />
            </div>
            <div>
              <div className="product-brand">{o.brand}</div>
              <a className="order-row-name" href={`#/product/${o.product_id}`}>{o.product_name.replace(o.brand, "").trim()}</a>
              <div className="bag-meta">Size {o.size} · {o.color} · Qty {o.quantity}</div>
              <div className="detail-prices">
                <strong>{money(o.price)}</strong>
                {o.mrp > o.price && <s>{money(o.mrp)}</s>}
              </div>
            </div>
          </div>

          <dl className="order-facts wide">
            <div><dt>Payment</dt><dd>{o.payment_method} · {humanize(o.payment_status)}</dd></div>
            <div><dt>{delivered ? "Delivered" : o.cancelled_date ? "Cancelled" : "Expected"}</dt><dd>{formatDate(o.delivery_date ?? o.cancelled_date ?? o.expected_delivery_date)}</dd></div>
            <div><dt>Carrier</dt><dd>{t.carrier}</dd></div>
            <div><dt>Tracking ID</dt><dd>{t.tracking_id}</dd></div>
          </dl>
          {late && <div className="notice warn">This order is past its expected delivery date of {formatDate(o.expected_delivery_date)}.</div>}

          <h2>Tracking</h2>
          <Timeline events={t.events} status={o.status} />

          <div className="detail-actions">
            {(o.status === "delivered" || upcoming) && <a className="btn-outline" href={supportLink(o.order_id, "track")}>Track with SupportAI</a>}
            {e.cancellation.eligible && <a className="btn-outline" href={supportLink(o.order_id, "cancel")}>Cancel order</a>}
            {e.return.eligible && <a className="btn-outline" href={supportLink(o.order_id, "return")}>Return</a>}
            {e.exchange.eligible && <a className="btn-outline" href={supportLink(o.order_id, "exchange")}>Exchange</a>}
            <a className="btn-solid" href={supportLink(o.order_id)}>
              <LifeBuoy size={16} /> Get help
            </a>
          </div>
        </section>

        <aside className="panel">
          <h2>Eligibility</h2>
          <p className="muted-text">Computed by the same rules the support assistant uses.</p>
          {delivered || ["return_initiated", "returned", "exchange_initiated"].includes(o.status) ? (
            <>
              <EligibilityRow label="Return" part={e.return} />
              <EligibilityRow label="Exchange" part={e.exchange} />
            </>
          ) : null}
          {upcoming && <EligibilityRow label="Cancellation" part={e.cancellation} />}
          {o.status === "cancelled" && <EligibilityRow label="Refund" part={e.refund} />}
        </aside>
      </div>
    </div>
  );
}
