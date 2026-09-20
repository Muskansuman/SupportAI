import { Check, X } from "lucide-react";
import { TONE_ICON } from "./ResultCard";
import DecisionPanel from "./DecisionPanel";

const TONE_LABEL = { success: "Done", info: "Update", warning: "Not available", escalated: "Escalated", neutral: "Update" };

// Customer view of the right-hand panel: the result and why, in plain
// language. The technical detail sits in a collapsed "AI details" section.
export default function CustomerPanel({ result, pending, pendingSteps, onHuman, busy, onOpenPolicies }) {
  const summary = result?.customer_summary;
  const last = pendingSteps[pendingSteps.length - 1];
  const Icon = summary ? TONE_ICON[summary.tone] : null;
  const clarify = result?.clarification;

  return (
    <div className="customer-panel">
      <div className="cp-card">
        <div className="cp-title">Your result</div>

        {pending && <p className="panel-empty">{last ? `${last.label}…` : "Checking your request…"}</p>}

        {!pending && !result && <p className="panel-empty">Ask a question and the outcome appears here, with the reason behind it.</p>}

        {!pending && summary && (
          <>
            <div className={`cp-result tone-${summary.tone}`}>
              <Icon size={18} />
              <div>
                <strong>{summary.title}</strong>
                <span className="cp-chip">{TONE_LABEL[summary.tone]}</span>
              </div>
            </div>

            {summary.why.length > 0 && (
              <div className="cp-section">
                <div className="result-label">{summary.why_heading}</div>
                <ul className="why-list">
                  {summary.why.map((w) => (
                    <li key={w.text} className={w.passed ? "pass" : "fail"}>
                      {w.passed ? <Check size={14} /> : <X size={14} />}
                      <span>{w.text}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="cp-section">
              <div className="result-label">{summary.refund ? "Refund" : "Next step"}</div>
              {summary.refund ? (
                <dl className="refund-facts compact">
                  <dt>Amount</dt>
                  <dd>{summary.refund.amount}</dd>
                  <dt>To</dt>
                  <dd>{summary.refund.method}</dd>
                  <dt>When</dt>
                  <dd>{summary.refund.timeline}</dd>
                </dl>
              ) : (
                <p className="cp-text">{summary.next_steps[0]}</p>
              )}
            </div>
          </>
        )}

        {!pending && result && !summary && (
          <div className="cp-section">
            <p className="cp-text">{clarify ? "I need one more detail before I can act." : result.knowledge_grounded ? "Answered from the help center." : "Answered."}</p>
          </div>
        )}

        <div className="cp-actions">
          <a className="btn-outline sm" href="#/orders">
            View My Orders
          </a>
          <button type="button" className="btn-outline sm" onClick={onHuman} disabled={busy}>
            Talk to a human
          </button>
        </div>
      </div>

      <details className="ai-details">
        <summary>Why this decision? (AI details)</summary>
        <DecisionPanel result={result} pending={pending} pendingSteps={pendingSteps} onOpenPolicies={onOpenPolicies} onHuman={onHuman} busy={busy} embedded />
      </details>
    </div>
  );
}
