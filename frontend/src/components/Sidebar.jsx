import { useState } from "react";
import {
  BookOpen,
  Bot,
  Boxes,
  ChartColumn,
  ChevronDown,
  Headset,
  History,
  Info,
  MessageSquarePlus,
  PlayCircle,
  ShieldCheck,
  X,
} from "lucide-react";

const CATEGORIES = [
  { title: "Orders", items: [["Track my order", "Where is my order?"], ["Cancel an order", "I want to cancel my order."]] },
  { title: "Returns & refunds", items: [["Return an item", "I want to return my order."], ["Exchange a size", "I want to exchange my order for size L."], ["Refund status", "Where is my refund?"]] },
  { title: "Problems", items: [["Delivery issue", "My order hasn't arrived yet."], ["Payment issue", "I was charged but my order was cancelled."], ["Damaged product", "My product arrived damaged."], ["Wrong product", "I received a different product than what I ordered."]] },
  { title: "Help", items: [["Size guide", "How do I find my size?"], ["Talk to a human", "I want to talk to a human agent."]] },
];

const VISIBLE_SCENARIOS = 5;

export default function Sidebar({ conversations, activeId, loadingIds, scenarios, meta, open, onClose, onNew, onSelect, onScenario, onCategory, onOpenPanel }) {
  const [allScenarios, setAllScenarios] = useState(false);
  const [showCategories, setShowCategories] = useState(false);
  const shownScenarios = allScenarios ? scenarios : scenarios.slice(0, VISIBLE_SCENARIOS);
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="sidebar-scroll">
        <div className="sidebar-brand">
          <div className="brand-logo">
            <Bot size={22} />
          </div>
          <div className="brand-text">
            <div className="brand-name">Help Center</div>
            <div className="brand-subtitle">How can we help?</div>
          </div>
          <button type="button" className="icon-btn sidebar-close" onClick={onClose} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <div className="demo-badge">
          <ShieldCheck size={14} /> Synthetic Demo Environment
        </div>

        <button type="button" className="new-chat-btn" onClick={onNew}>
          <MessageSquarePlus size={17} /> New chat
        </button>

        <div className="sidebar-section">
          <div className="sidebar-heading">
            <PlayCircle size={14} /> Try demo scenarios
          </div>
          <div className="scenario-list">
            {shownScenarios.map((s) => (
              <button key={s.id} type="button" className="scenario-btn" onClick={() => onScenario(s)} title={s.message}>
                <span className="scenario-title">{s.title}</span>
                <span className="scenario-message">{s.message}</span>
              </button>
            ))}
          </div>
          {scenarios.length > VISIBLE_SCENARIOS && (
            <button type="button" className="link-btn view-all" onClick={() => setAllScenarios((v) => !v)}>
              {allScenarios ? "Show fewer scenarios" : `View all scenarios (${scenarios.length})`}
            </button>
          )}
        </div>

        <div className="sidebar-section">
          <button type="button" className="sidebar-heading heading-toggle" onClick={() => setShowCategories((v) => !v)} aria-expanded={showCategories}>
            <Boxes size={14} /> Support categories <ChevronDown size={14} className={showCategories ? "rot" : ""} />
          </button>
          {showCategories && CATEGORIES.map((c) => (
            <div key={c.title} className="category">
              <div className="category-title">{c.title}</div>
              <div className="category-items">
                {c.items.map(([label, text]) => (
                  <button key={label} type="button" className="category-chip" onClick={() => onCategory(text)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-heading">
            <History size={14} /> Recent chats
          </div>
          <div className="conversations-list">
            {conversations.map((c) => (
              <button key={c.id} type="button" className={`conversation-item ${c.id === activeId ? "active" : ""}`} onClick={() => onSelect(c.id)}>
                {loadingIds.has(c.id) && <span className="conversation-loading-dot" />}
                {c.title}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="sidebar-footer">
        {meta?.demo_customer && (
          <div className="customer-card">
            <div className="customer-label">Signed in as (demo)</div>
            <div className="customer-name">{meta.demo_customer.name}</div>
            <div className="customer-id">
              {meta.demo_customer.customer_id} · {meta.demo_customer.city}
            </div>
          </div>
        )}
        <div className="footer-links">
          <button type="button" onClick={() => onOpenPanel("policies")}>
            <BookOpen size={14} /> Help center
          </button>
          <button type="button" onClick={() => onOpenPanel("evaluation")}>
            <ChartColumn size={14} /> Evaluation
          </button>
          <button type="button" onClick={() => onOpenPanel("about")}>
            <Info size={14} /> About
          </button>
        </div>
      </div>
    </aside>
  );
}
