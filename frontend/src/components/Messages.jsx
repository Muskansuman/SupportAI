import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, FileText, Headset, RotateCw, ThumbsDown, ThumbsUp, User } from "lucide-react";
import OrderCard from "./OrderCard";
import ResultCard from "./ResultCard";
import { ACTION_LABELS, INTENT_LABELS, formatTime } from "../utils";

// Raw HTML in model output is never rendered (react-markdown's default), so
// this stays safe without an extra sanitizer.
const MARKDOWN_COMPONENTS = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  table: ({ node: _node, ...props }) => (
    <div className="md-table-wrap">
      <table {...props} />
    </div>
  ),
};

function Markdown({ text }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function Avatar({ role }) {
  return <div className={`avatar avatar-${role}`}>{role === "user" ? <User size={16} /> : <Bot size={16} />}</div>;
}

export function UserMessage({ message }) {
  return (
    <div className="message-row user">
      <div className="message-content">
        <div className="bubble user">{message.content}</div>
        <div className="message-timestamp">{formatTime(message.timestamp)}</div>
      </div>
      <Avatar role="user" />
    </div>
  );
}

export function ErrorMessage({ message, onRetry, canRetry }) {
  return (
    <div className="message-row assistant">
      <Avatar role="assistant" />
      <div className="message-content">
        <div className="bubble assistant bubble-error">{message.content}</div>
        {canRetry && (
          <button type="button" className="retry-btn" onClick={onRetry}>
            <RotateCw size={13} /> Try again
          </button>
        )}
      </div>
    </div>
  );
}

function EscalationCard({ result }) {
  const [continued, setContinued] = useState(false);
  const reference = result.demo_action?.reference;
  return (
    <div className="escalation-card">
      <div className="escalation-head">
        <Headset size={15} /> Human support
      </div>
      <div className="escalation-body">
        <strong>Escalation prepared</strong>
        <dl className="escalation-facts">
          <dt>Reason</dt>
          <dd>{result.escalation_reason}</dd>
          {reference && (
            <>
              <dt>Reference</dt>
              <dd className="mono">{reference}</dd>
            </>
          )}
        </dl>
      </div>
      {continued ? (
        <div className="escalation-done">Demo escalation request created successfully. This is simulated: no real agent is connected.</div>
      ) : (
        <button type="button" className="btn-primary" onClick={() => setContinued(true)}>
          Continue to Human Support
        </button>
      )}
    </div>
  );
}

export function AssistantMessage({ message, isLast, busy, view, onChoose, onSelectSize, onFeedback, onHuman }) {
  const r = message.result;
  const interactive = isLast && !busy;
  const action = r.recommended_action;

  return (
    <div className="message-row assistant">
      <Avatar role="assistant" />
      <div className="message-content">
        {!r.local && view === "diagnostics" && (
          <div className="tag-row">
            <span className="tag">{INTENT_LABELS[r.intent] ?? r.intent}</span>
            <span className={`tag urgency-tag urgency-${r.urgency.toLowerCase()}`}>{r.urgency.charAt(0) + r.urgency.slice(1).toLowerCase()} urgency</span>
            <span className={`tag action-tag action-${action}`}>{ACTION_LABELS[action]}</span>
          </div>
        )}

        <div className="bubble assistant answer-bubble">
          <Markdown text={r.message} />
          {r.knowledge_grounded && r.sources.length > 0 && (
            <div className="answer-sources">
              <span className="answer-sources-label">Sources:</span>
              {r.sources.map((s) => (
                <span key={`${s.id}-${s.section}`} className="source-chip">
                  <FileText size={12} /> {s.title}
                </span>
              ))}
            </div>
          )}
        </div>

        {r.order && (
          <OrderCard
            order={r.order}
            intent={r.intent}
            eligibility={r.eligibility}
            selectedSize={r.entities?.requested_size}
            onSelectSize={interactive ? (size) => onSelectSize(message, size) : () => {}}
            disabled={!interactive}
          />
        )}

        {r.customer_summary && <ResultCard summary={r.customer_summary} onHuman={onHuman} interactive={interactive} />}

        {r.clarification && !(r.order && (r.outcome === "NEEDS_SIZE" || r.outcome === "SIZE_UNAVAILABLE")) && (
          <div className="options-row">
            {r.clarification.options.map((o) => (
              <button key={o.value} type="button" className="option-chip" disabled={!interactive} onClick={() => onChoose(message, o)}>
                {o.label}
              </button>
            ))}
          </div>
        )}

        {r.demo_action && !r.customer_summary && r.demo_action.type !== "ESCALATION_PREPARED" && (
          <div className="demo-action">
            <strong>Demo action:</strong> {r.demo_action.reference} · {r.demo_action.note}
          </div>
        )}

        {r.escalation_needed && <EscalationCard result={r} />}

        {r.warnings?.length > 0 && <div className="warning-note">{r.warnings.join(" · ")}</div>}

        {!r.local && (
          <div className="answer-meta">
            <span className="feedback-buttons">
              <button type="button" className={`feedback-btn ${message.feedback === "up" ? "active" : ""}`} onClick={() => onFeedback(message.id, "up")} aria-label="Good response">
                <ThumbsUp size={14} />
              </button>
              <button type="button" className={`feedback-btn ${message.feedback === "down" ? "active" : ""}`} onClick={() => onFeedback(message.id, "down")} aria-label="Bad response">
                <ThumbsDown size={14} />
              </button>
            </span>
            <span className="latency">Answered in {(r.latency_ms / 1000).toFixed(1)}s</span>
            <span className="message-timestamp">{formatTime(message.timestamp)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function PendingMessage({ steps }) {
  const last = steps[steps.length - 1];
  return (
    <div className="message-row assistant">
      <Avatar role="assistant" />
      <div className="message-content">
        <div className="bubble assistant bubble-loading">
          <span className="dots">
            <i />
            <i />
            <i />
          </span>
          {last ? last.label : "Reading your message"}…
        </div>
      </div>
    </div>
  );
}
