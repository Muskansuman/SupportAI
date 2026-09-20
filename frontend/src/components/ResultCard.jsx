import { AlertTriangle, CheckCircle2, Headset, Info, MinusCircle } from "lucide-react";

export const TONE_ICON = { success: CheckCircle2, info: Info, warning: AlertTriangle, escalated: Headset, neutral: MinusCircle };

// The outcome as the customer needs it: what was decided, what happens next,
// any refund, and the demo reference. Diagnostic detail lives elsewhere.
export default function ResultCard({ summary, onHuman, interactive }) {
  const Icon = TONE_ICON[summary.tone] ?? Info;
  const showReference = summary.reference && summary.tone !== "escalated";
  return (
    <div className={`result-card tone-${summary.tone}`}>
      <div className="result-head">
        <Icon size={18} />
        <strong>{summary.title}</strong>
      </div>

      <div className="result-section">
        <div className="result-label">What happens next</div>
        <ul>
          {summary.next_steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>

      {summary.refund && (
        <dl className="refund-facts">
          <dt>Refund amount</dt>
          <dd>{summary.refund.amount}</dd>
          <dt>Refund to</dt>
          <dd>{summary.refund.method}</dd>
          <dt>Timeline</dt>
          <dd>{summary.refund.timeline}</dd>
        </dl>
      )}

      {showReference && (
        <div className="result-ref">
          Demo reference <span className="mono">{summary.reference}</span>
          <span className="result-ref-note"> · simulated, no real request is made</span>
        </div>
      )}

      {(summary.order_id || summary.tone === "warning") && (
        <div className="result-actions">
          {summary.order_id && (
            <a className="btn-outline sm" href={`#/orders/${summary.order_id}`}>
              View order
            </a>
          )}
          {summary.tone === "warning" && (
            <button type="button" className="btn-outline sm" onClick={onHuman} disabled={!interactive}>
              Talk to a human
            </button>
          )}
        </div>
      )}
    </div>
  );
}
