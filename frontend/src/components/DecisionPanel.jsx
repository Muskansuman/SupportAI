import { useState } from "react";
import {
  Ban,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Circle,
  Headset,
  Info,
  Loader2,
  MinusCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { ACTION_LABELS, INTENT_LABELS, STEP_ORDER, formatDate, humanize, money } from "../utils";

function Workflow({ steps, running }) {
  const byKey = Object.fromEntries(steps.map((s) => [s.key, s]));
  const firstPending = STEP_ORDER.findIndex((s) => !byKey[s.key]);
  return (
    <ol className="workflow">
      {STEP_ORDER.map((def, i) => {
        const step = byKey[def.key];
        const state = step ? step.status : running && i === firstPending ? "running" : "pending";
        const Icon = state === "done" ? CheckCircle2 : state === "skipped" ? MinusCircle : state === "running" ? Loader2 : Circle;
        return (
          <li key={def.key} className={`workflow-step ${state}`}>
            <Icon size={15} className={state === "running" ? "spin" : ""} />
            <div>
              <div className="workflow-label">{def.label}</div>
              {step?.detail && <div className="workflow-detail">{step.detail}</div>}
            </div>
            {step && step.duration_ms > 0 && <span className="workflow-ms">{step.duration_ms < 1000 ? `${Math.round(step.duration_ms)} ms` : `${(step.duration_ms / 1000).toFixed(1)} s`}</span>}
          </li>
        );
      })}
    </ol>
  );
}

function Source({ source }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="source">
      <button type="button" className="source-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <BookOpen size={14} />
        <span>
          {source.title}
          <span className="source-section"> · {source.section}</span>
        </span>
        <span className="source-score">{source.score.toFixed(2)}</span>
        <ChevronDown size={14} className={open ? "rot" : ""} />
      </button>
      {open && <p className="source-excerpt">{source.excerpt}</p>}
    </li>
  );
}

const BAND_LABEL = { HIGH: "High", MEDIUM: "Medium", LOW: "Low" };

function Card({ title, badge, defaultOpen = false, tone, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`acc ${tone ? `acc-${tone}` : ""}`}>
      <button type="button" className="acc-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span>{title}</span>
        {badge != null && <span className="acc-badge">{badge}</span>}
        <ChevronDown size={15} className={open ? "rot" : ""} />
      </button>
      {open && <div className="acc-body">{children}</div>}
    </section>
  );
}

const cap = (t) => t.charAt(0) + t.slice(1).toLowerCase();

export default function DecisionPanel({ result, pendingSteps, pending, onOpenPolicies, onHuman, busy, embedded }) {
  const showResult = !!result && !pending;
  const steps = pending ? pendingSteps : result?.workflow_steps ?? [];
  const band = result?.confidence_band;
  const action = result?.recommended_action;
  const signals = result?.reasoning_signals ?? [];
  const demo = result?.demo_action;
  const escalation = showResult && result.escalation_needed;

  return (
    <div className="decision-panel">
      <div className="panel-title ai-title">
        <Sparkles size={16} /> AI Decision Engine
        <span className="ai-tag">Diagnostics</span>
      </div>

      {showResult ? (
        <div className="summary-grid">
          <div className="metric wide">
            <span className="metric-label">Intent</span>
            <span className="metric-value">{INTENT_LABELS[result.intent] ?? result.intent}</span>
            <span className="metric-sub mono">{result.intent}</span>
          </div>
          <div className="metric">
            <span className="metric-label">
              Confidence
              <span className="hint" title="Confidence in the predicted support intent." aria-label="Confidence in the predicted support intent.">
                <Info size={12} />
              </span>
            </span>
            <span className={`band band-${band?.toLowerCase()}`}>{BAND_LABEL[band] ?? band}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Urgency</span>
            <span className={`metric-value urgency-${result.urgency.toLowerCase()}`}>{cap(result.urgency)}</span>
          </div>
          <div className="metric wide">
            <span className="metric-label">Recommended action</span>
            <span className={`action-pill action-${action}`}>{ACTION_LABELS[action]}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Escalation</span>
            <span className="metric-value">{result.escalation_needed ? <span className="no">Yes</span> : <span className="yes">No</span>}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Grounded</span>
            <span className="metric-value">
              {result.knowledge_grounded ? <span className="yes">Yes</span> : <span className="muted">No</span>}
              <span className="metric-inline"> · {result.knowledge_grounded ? result.sources.length : 0} sources</span>
            </span>
          </div>
        </div>
      ) : (
        <p className="panel-empty">{pending ? "Working through your request…" : "Send a message to see how SupportAI reasons about it."}</p>
      )}

      <div className="acc-list">
        {pending && (
          <Card title="Workflow" defaultOpen>
            <Workflow steps={steps} running />
          </Card>
        )}

        {showResult && (
          <Card title="Reasoning signals" badge={signals.length} defaultOpen={signals.length <= 4}>
            <ul className="signals">
              {signals.map((sig, i) => {
                const failed = sig.startsWith("✗");
                return (
                  <li key={i} className={failed ? "signal-fail" : ""}>
                    {failed ? <Ban size={13} /> : <ShieldCheck size={13} />}
                    {sig.replace(/^[✓✗]\s*/, "")}
                  </li>
                );
              })}
            </ul>
          </Card>
        )}

        {showResult && (
          <Card title="Sources" badge={result.sources.length}>
            {result.sources.length ? (
              <ul className="sources">
                {result.sources.map((src) => (
                  <Source key={`${src.id}-${src.section}`} source={src} />
                ))}
              </ul>
            ) : (
              <p className="panel-empty">No policy passages were retrieved for this request.</p>
            )}
            {result.sources.length > 0 && !result.knowledge_grounded && <p className="panel-note">Retrieved, but the built-in response was used instead of writing from them.</p>}
            <button type="button" className="link-btn" onClick={onOpenPolicies}>
              Browse all policies
            </button>
          </Card>
        )}

        <Card title="Order information" badge={result?.order ? result.order.order_id : "none"}>
          {result?.order ? (
            <div className="order-info">
              <dl>
                <dt>Order ID</dt>
                <dd>{result.order.order_id}</dd>
                <dt>Status</dt>
                <dd>{humanize(result.order.status)}</dd>
                <dt>Order date</dt>
                <dd>{formatDate(result.order.order_date)}</dd>
                <dt>Amount</dt>
                <dd>{money(result.order.price)}</dd>
                <dt>Payment</dt>
                <dd>{humanize(result.order.payment_status)}</dd>
              </dl>
              <a className="btn-outline sm" href={`#/orders/${result.order.order_id}`}>
                Track order
              </a>
            </div>
          ) : (
            <div className="order-info">
              <p className="panel-empty">No order selected.</p>
              <a className="btn-outline sm" href="#/orders">
                View my orders
              </a>
            </div>
          )}
        </Card>

        {escalation && (
          <Card title="Escalation details" tone="alert">
            <dl className="esc-dl">
              <dt>Reason</dt>
              <dd>{result.escalation_reason}</dd>
              {demo && (
                <>
                  <dt>Reference</dt>
                  <dd className="mono">{demo.reference}</dd>
                </>
              )}
            </dl>
            <p className="panel-note">Simulated: no real agent is connected.</p>
          </Card>
        )}

        {!pending && steps.length > 0 && (
          <Card title="Workflow" badge={`${(result.latency_ms / 1000).toFixed(1)} s`}>
            <Workflow steps={steps} running={false} />
          </Card>
        )}
      </div>

      {!embedded && (
      <div className="human-help">
        <span>Need more help?</span>
        <button type="button" className="btn-outline sm" onClick={onHuman} disabled={busy}>
          <Headset size={14} /> Human support
        </button>
      </div>
      )}
    </div>
  );
}
