import { useEffect, useState } from "react";
import { BookOpen, ChartColumn, Info, X } from "lucide-react";
import { getEvaluation, getKnowledge } from "../api";
import { INTENT_LABELS } from "../utils";

const pct = (x) => (x == null ? "-" : `${(x * 100).toFixed(1)}%`);

function Heatmap({ confusion }) {
  const { labels, matrix } = confusion;
  const max = Math.max(1, ...matrix.flat());
  const short = (l) => l.split("_").map((w) => w[0]).join("");
  return (
    <div className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr>
            <th className="corner">gold ↓ / predicted →</th>
            {labels.map((l) => (
              <th key={l} title={INTENT_LABELS[l] ?? l}>
                {short(l)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <th title={INTENT_LABELS[labels[i]] ?? labels[i]}>{INTENT_LABELS[labels[i]] ?? labels[i]}</th>
              {row.map((n, j) => (
                <td key={j} className={i === j ? "diag" : ""} style={{ background: n ? `rgba(79, 70, 229, ${0.12 + 0.78 * (n / max)})` : "transparent", color: n / max > 0.5 ? "#fff" : undefined }}>
                  {n || ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SplitReport({ name, data }) {
  const { intent, urgency, escalation, decision, confidence, entities } = data;
  const cards = [
    ["Intent accuracy", pct(intent.accuracy)],
    ["Intent macro F1", intent.macro_f1.toFixed(3)],
    ["Urgency accuracy", pct(urgency.accuracy)],
    ["Escalation precision", pct(escalation.precision)],
    ["Escalation recall", pct(escalation.recall)],
    ["Decision accuracy", pct(decision.accuracy)],
    ["Unsafe auto-resolve", pct(decision.unsafe_auto_resolve_rate)],
    ["Over-cautious", pct(decision.over_cautious_rate)],
  ];
  return (
    <section className="eval-split">
      <h3>
        {name === "test" ? "Seen phrasings" : "Unseen phrasings"} <span className="muted">n = {data.n}</span>
      </h3>
      <p className="eval-desc">{name === "test" ? "Held-out conversations that share phrasing templates with the training data." : "Phrasings that were never in the training data: the honest generalisation check."}</p>
      <div className="eval-cards">
        {cards.map(([label, value]) => (
          <div key={label} className="eval-card">
            <div className="eval-value">{value}</div>
            <div className="eval-label">{label}</div>
          </div>
        ))}
      </div>

      <h4>Does confidence track correctness?</h4>
      <table className="eval-table">
        <thead>
          <tr>
            <th>Confidence band</th>
            <th>Predictions</th>
            <th>Intent accuracy</th>
          </tr>
        </thead>
        <tbody>
          {["HIGH", "MEDIUM", "LOW"].map((b) => (
            <tr key={b}>
              <td>{b.toLowerCase()}</td>
              <td>{confidence.by_band[b].n}</td>
              <td>{pct(confidence.by_band[b].accuracy)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="eval-desc">Calibration error (ECE): {confidence.ece.toFixed(3)} · mean confidence {pct(confidence.mean_confidence)} · regex entity recall: order ID {pct(entities.order_id_recall)}, size {pct(entities.size_recall)}</p>

      <h4>Per-intent precision / recall / F1</h4>
      <table className="eval-table">
        <thead>
          <tr>
            <th>Intent</th>
            <th>P</th>
            <th>R</th>
            <th>F1</th>
            <th>n</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(intent.per_class).map(([k, v]) => (
            <tr key={k}>
              <td>{INTENT_LABELS[k] ?? k}</td>
              <td>{v.precision.toFixed(2)}</td>
              <td>{v.recall.toFixed(2)}</td>
              <td>{v.f1.toFixed(2)}</td>
              <td>{v.support}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>Intent confusion matrix</h4>
      <Heatmap confusion={intent.confusion} />
    </section>
  );
}

function Evaluation() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    getEvaluation().then(setData).catch((e) => setError(e.message));
  }, []);
  if (error) return <p className="panel-empty">{error}</p>;
  if (!data) return <p className="panel-empty">Loading…</p>;
  return (
    <div>
      <div className="eval-notes">
        {data.notes.map((n, i) => (
          <p key={i}>{n}</p>
        ))}
      </div>
      <SplitReport name="test" data={data.splits.test} />
      <SplitReport name="test_unseen" data={data.splits.test_unseen} />
      <p className="eval-desc">Generated {data.generated_at} from {data.dataset.counts.support_conversations.toLocaleString()} synthetic conversations (seed {data.dataset.seed}).</p>
    </div>
  );
}

function Policies({ highlight }) {
  const [docs, setDocs] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    getKnowledge().then(setDocs).catch((e) => setError(e.message));
  }, []);
  if (error) return <p className="panel-empty">{error}</p>;
  if (!docs) return <p className="panel-empty">Loading…</p>;
  return (
    <div className="policy-list">
      {docs.map((d) => (
        <div key={d.id} className={`policy-item ${d.id === highlight ? "highlighted" : ""}`}>
          <div className="policy-title">{d.title}</div>
          {d.sections.map((s) => (
            <div key={s.heading} className="policy-section">
              <div className="policy-heading">{s.heading}</div>
              <p>{s.text}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function About({ meta }) {
  return (
    <div className="about">
      <p className="about-notice">{meta?.about ?? "All customer, product and order information shown in this demo is synthetic data created for demonstration purposes."}</p>
      <h4>What happens to a message</h4>
      <ol className="about-steps">
        <li>A fine-tuned Qwen2.5-0.5B classifier (LoRA) labels the <strong>intent</strong> and <strong>urgency</strong>. Its confidence is the model's own token probability.</li>
        <li>Order IDs and sizes are pulled out with regexes, and the order is fetched from a database lookup, never guessed by the model.</li>
        <li>Deterministic rules check <strong>eligibility</strong> (return, exchange, cancellation, refund windows) against the order data.</li>
        <li>A <strong>decision engine</strong> chooses to auto-resolve, ask a clarifying question, or hand off to a human. Urgency and escalation are separate concepts.</li>
        <li>Relevant <strong>policy passages</strong> are retrieved from a vector store, and an LLM writes the reply only from the facts and passages it is given.</li>
      </ol>
      <h4>Honest limits</h4>
      <ul>
        <li>No real store, customer or agent is connected. Actions are simulated and reference IDs are marked demo.</li>
        <li>The conversations used for training and evaluation are template-generated, so measured accuracy is not real-world accuracy. See the Evaluation tab.</li>
        <li>Brands and people are fictional. This project is not affiliated with any retailer.</li>
      </ul>
      {meta && (
        <p className="about-meta">
          Dataset: {meta.counts.products.toLocaleString()} products · {meta.counts.customers.toLocaleString()} customers · {meta.counts.orders.toLocaleString()} orders · {meta.counts.support_conversations.toLocaleString()} conversations · {meta.counts.knowledge_base} policy documents. Demo clock: {new Date(meta.demo_clock).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}.
        </p>
      )}
    </div>
  );
}

const TABS = [
  ["about", "About", Info],
  ["policies", "Policies", BookOpen],
  ["evaluation", "Evaluation", ChartColumn],
];

export default function InfoPanel({ tab, onTab, onClose, meta, highlight }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="overlay-panel" onClick={(e) => e.stopPropagation()}>
        <div className="overlay-header">
          <div className="tabs">
            {TABS.map(([key, label, Icon]) => (
              <button key={key} type="button" className={`tab ${tab === key ? "active" : ""}`} onClick={() => onTab(key)}>
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="overlay-body">
          {tab === "about" && <About meta={meta} />}
          {tab === "policies" && <Policies highlight={highlight} />}
          {tab === "evaluation" && <Evaluation />}
        </div>
      </div>
    </div>
  );
}
