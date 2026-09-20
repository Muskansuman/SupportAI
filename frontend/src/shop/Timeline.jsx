import { Check } from "lucide-react";
import { formatDate, humanize } from "../utils";

const FLOW = ["ORDER_PLACED", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"];
const LABEL = { ORDER_PLACED: "Order placed", PACKED: "Packed", SHIPPED: "Shipped", OUT_FOR_DELIVERY: "Out for delivery", DELIVERED: "Delivered" };

// Steps that really happened come from the tracking events; later steps stay
// pending. Cancelled and returned orders show their own terminal step.
export default function Timeline({ events, status }) {
  const byStatus = Object.fromEntries(events.map((e) => [e.status, e]));
  const extra = events.filter((e) => !FLOW.includes(e.status) && e.status !== "CONFIRMED");
  const steps = FLOW.map((key) => ({ key, label: LABEL[key], event: byStatus[key] }));
  const lastDone = steps.reduce((n, s, i) => (s.event ? i : n), -1);

  return (
    <ol className="timeline" aria-label="Order tracking">
      {steps.map((s, i) => {
        const done = !!s.event;
        const current = i === lastDone && status !== "delivered" && status !== "cancelled";
        return (
          <li key={s.key} className={`${done ? "done" : ""} ${current ? "current" : ""}`}>
            <span className="tl-dot">{done && !current ? <Check size={13} /> : null}</span>
            <div>
              <strong>{s.label}</strong>
              {s.event ? (
                <small>
                  {formatDate(s.event.timestamp)} · {s.event.location}
                </small>
              ) : (
                <small>Pending</small>
              )}
            </div>
          </li>
        );
      })}
      {extra.map((e) => (
        <li key={e.status + e.timestamp} className="done extra">
          <span className="tl-dot">
            <Check size={13} />
          </span>
          <div>
            <strong>{humanize(e.status.toLowerCase())}</strong>
            <small>
              {formatDate(e.timestamp)} · {e.location}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}
