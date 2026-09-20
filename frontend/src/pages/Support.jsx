import { useEffect, useRef, useState } from "react";
import { ArrowLeftRight, Bot, Headset, IndianRupee, Info, Menu, PackageSearch, PanelRight, Ruler, Send, ShieldCheck, X, XCircle } from "lucide-react";
import { getScenarios, resolveStream } from "../api";
import CustomerPanel from "../components/CustomerPanel";
import DecisionPanel from "../components/DecisionPanel";
import InfoPanel from "../components/InfoPanel";
import { AssistantMessage, ErrorMessage, PendingMessage, UserMessage } from "../components/Messages";
import Sidebar from "../components/Sidebar";
import { makeId } from "../utils";

const QUICK_ACTIONS = [
  ["Track my order", "Where is my order?", PackageSearch],
  ["Return / Exchange", "I want to return or exchange my order.", ArrowLeftRight],
  ["Cancel an order", "I want to cancel my order.", XCircle],
  ["Refund", "I want a refund for my order.", IndianRupee],
  ["Size & Fit Help", "How do I find my size?", Ruler],
  ["Talk to a human", "I want to talk to a human agent.", Headset],
];

const VIEW_KEY = "supportai_view";

const STORAGE_KEY = "supportai_fashion_v1";
const MAX_CONVERSATIONS = 20;
const MAX_MESSAGES = 40;

const makeConversation = () => {
  const now = new Date().toISOString();
  return { id: makeId(), title: "New conversation", messages: [], createdAt: now, updatedAt: now };
};

function loadStore() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved?.conversations?.length > 0) return saved;
  } catch {
    // unreadable or old-format data: start fresh
  }
  const initial = makeConversation();
  return { conversations: [initial], activeId: initial.id };
}

// Choices made earlier in this issue (order, size, confirmed intent) carry
// forward, so answering a second question doesn't forget the first answer.
const carried = (request) => {
  const { order_id, selected_size, intent_override } = request ?? {};
  return Object.fromEntries(Object.entries({ order_id, selected_size, intent_override }).filter(([, v]) => v));
};

export default function Support({ meta, health, healthError, context }) {
  const [scenarios, setScenarios] = useState([]);
  const [view, setViewState] = useState(() => {
    try {
      return localStorage.getItem(VIEW_KEY) === "diagnostics" ? "diagnostics" : "customer";
    } catch {
      return "customer";
    }
  });
  const setView = (v) => {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      // preference just isn't remembered
    }
  };
  const [store, setStore] = useState(loadStore);
  const [pending, setPending] = useState({});
  const [draft, setDraft] = useState("");
  const [showInfo, setShowInfo] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [overlay, setOverlay] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const infoRef = useRef(null);

  const { conversations, activeId } = store;
  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];
  const messages = active.messages;
  const activePending = pending[active.id];
  const sorted = [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const loadingIds = new Set(Object.keys(pending));
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const lastResult = [...messages].reverse().find((m) => m.role === "assistant" && m.result && !m.result.local)?.result;

  useEffect(() => {
    getScenarios().then(setScenarios).catch(() => {});
  }, [health]);

  useEffect(() => {
    try {
      const trimmed = {
        ...store,
        conversations: store.conversations.slice(0, MAX_CONVERSATIONS).map((c) => ({ ...c, messages: c.messages.slice(-MAX_MESSAGES) })),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch {
      // storage full or unavailable: the app still works, just without persistence
    }
  }, [store]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, activePending?.steps.length]);

  useEffect(() => {
    if (!showInfo) return;
    const close = (e) => infoRef.current && !infoRef.current.contains(e.target) && setShowInfo(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [showInfo]);

  function updateMessages(conversationId, updater) {
    setStore((prev) => ({
      ...prev,
      conversations: prev.conversations.map((c) => {
        if (c.id !== conversationId) return c;
        const next = updater(c.messages);
        const first = next.find((m) => m.role === "user");
        return { ...c, messages: next, title: first ? first.content.slice(0, 40) : c.title, updatedAt: new Date().toISOString() };
      }),
    }));
  }

  async function send(text, { echo, overrides = {}, attempts = 0, skipUser = false, conversationId = active.id } = {}) {
    if (!text.trim() || pending[conversationId]) return;

    if (!skipUser) {
      const userMessage = { id: makeId(), role: "user", content: echo ?? text, timestamp: new Date().toISOString() };
      updateMessages(conversationId, (prev) => [...prev, userMessage]);
    }
    setDraft("");
    setPending((p) => ({ ...p, [conversationId]: { steps: [] } }));

    const request = { message: text, customer_id: meta?.demo_customer?.customer_id, clarification_attempts: attempts, ...overrides };
    try {
      const result = await resolveStream(request, (step) =>
        setPending((p) => (p[conversationId] ? { ...p, [conversationId]: { steps: [...p[conversationId].steps, step] } } : p))
      );
      updateMessages(conversationId, (prev) => [...prev, { id: makeId(), role: "assistant", timestamp: new Date().toISOString(), request, result, feedback: null }]);
    } catch (err) {
      const content = err.isNetworkError
        ? "SupportAI is waking up. This may take up to 30 seconds. Please try again shortly."
        : `I couldn't complete that request (${err.message}). You can try again, or ask for a human agent.`;
      updateMessages(conversationId, (prev) => [...prev, { id: makeId(), role: "assistant", timestamp: new Date().toISOString(), request, error: true, content }]);
    } finally {
      setPending((p) => {
        const { [conversationId]: _done, ...rest } = p;
        return rest;
      });
    }
  }

  // A typed reply to a clarifying question counts as a follow-up, so the
  // assistant doesn't ask the same thing again forever.
  function sendTyped(text) {
    const last = lastAssistant;
    const following = last?.result?.clarification && !last.result.local;
    send(text, { attempts: following ? (last.request.clarification_attempts ?? 0) + 1 : 0 });
  }

  function handleChoose(message, option) {
    const r = message.result;
    const base = message.request;
    const attempts = (base.clarification_attempts ?? 0) + 1;
    const keep = carried(base);

    if (r.outcome === "NEEDS_ORDER" || r.outcome === "ORDER_NOT_FOUND") {
      return send(base.message, { echo: option.label, attempts, overrides: { ...keep, order_id: option.value } });
    }
    if (r.outcome === "NEEDS_SIZE" || r.outcome === "SIZE_UNAVAILABLE") {
      return send(base.message, { echo: `Size ${option.value}`, attempts, overrides: { ...keep, order_id: r.order?.order_id ?? base.order_id, selected_size: option.value, intent_override: "EXCHANGE_REQUEST" } });
    }
    if (r.outcome === "NEEDS_DETAIL") {
      const intent = meta?.detail_options?.find((o) => o.value === option.value)?.intent;
      return send(base.message, { echo: option.label, attempts, overrides: { ...keep, intent_override: intent } });
    }
    if (r.outcome === "CONFIRM_INTENT") {
      if (option.value === "yes") return send(base.message, { echo: "Yes", attempts, overrides: { ...keep, intent_override: r.intent } });
      // "No": ask what it is about, locally: nothing new to classify
      const options = (meta?.detail_options ?? []).map((o) => ({ value: o.value, label: o.label }));
      const local = {
        local: true,
        message: "No problem. What best describes the problem?",
        clarification: { question: "What best describes the problem?", options },
        outcome: "NEEDS_DETAIL",
        recommended_action: "CLARIFICATION_REQUIRED",
        intent: r.intent,
        urgency: "LOW",
        sources: [],
        entities: {},
        warnings: [],
        escalation_needed: false,
        knowledge_grounded: false,
        order: null,
      };
      updateMessages(active.id, (prev) => [
        ...prev,
        { id: makeId(), role: "user", content: option.label, timestamp: new Date().toISOString() },
        { id: makeId(), role: "assistant", timestamp: new Date().toISOString(), request: { ...base, clarification_attempts: attempts }, result: local },
      ]);
    }
  }

  function handleSelectSize(message, size) {
    const base = message.request;
    send(base.message, { echo: `Exchange to size ${size}`, overrides: { ...carried(base), order_id: message.result.order.order_id, selected_size: size, intent_override: "EXCHANGE_REQUEST" } });
  }

  function handleFeedback(id, value) {
    updateMessages(active.id, (prev) => prev.map((m) => (m.id === id ? { ...m, feedback: m.feedback === value ? null : value } : m)));
  }

  function retry(message) {
    updateMessages(active.id, (prev) => prev.filter((m) => m.id !== message.id));
    send(message.request.message, { skipUser: true, attempts: message.request.clarification_attempts, overrides: carried(message.request) });
  }

  function newChat() {
    const conversation = makeConversation();
    setStore((prev) => ({ conversations: [conversation, ...prev.conversations], activeId: conversation.id }));
    setDraft("");
    setSidebarOpen(false);
  }

  function selectChat(id) {
    setStore((prev) => ({ ...prev, activeId: id }));
    setSidebarOpen(false);
  }

  function prefill(text) {
    setDraft(text);
    setSidebarOpen(false);
    textareaRef.current?.focus();
  }

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendTyped(draft);
    }
  };

  // Arriving from an order or product page: start a fresh chat that already
  // knows which order it is about. The backend still classifies the message.
  const contextKey = context ? JSON.stringify(context) : null;
  const handledContext = useRef(null);
  useEffect(() => {
    if (!contextKey || !meta || handledContext.current === contextKey) return;
    handledContext.current = contextKey;
    window.history.replaceState(null, "", "#/support");
    if (context.order) {
      const conversation = makeConversation();
      setStore((prev) => ({ conversations: [conversation, ...prev.conversations], activeId: conversation.id }));
      const id = context.order;
      const text = { track: `Where is my order ${id}?`, return: `I want to return my order ${id}.`, exchange: `I want to exchange my order ${id}.`, cancel: `I want to cancel my order ${id}.` }[context.topic] ?? `I need help with my order ${id}.`;
      send(text, { conversationId: conversation.id, overrides: { order_id: id } });
    } else if (context.productName) {
      newChat();
      setDraft(`I have a question about ${context.productName}`);
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }, [contextKey, meta]);

  const busy = !!activePending;
  const offline = healthError && !health;

  return (
    <div className="app-shell in-shop">
      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}
      <Sidebar
        conversations={sorted}
        activeId={active.id}
        loadingIds={loadingIds}
        scenarios={scenarios}
        meta={meta}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNew={newChat}
        onSelect={selectChat}
        onScenario={(s) => {
          setSidebarOpen(false);
          send(s.message);
        }}
        onCategory={prefill}
        onOpenPanel={(tab) => {
          setSidebarOpen(false);
          setOverlay({ tab });
        }}
      />

      <main className="main-column">
        <header className="main-header">
          <button type="button" className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div className="header-titles" ref={infoRef}>
            <div className="title-row">
              <h1>SupportAI Assistant</h1>
              <button type="button" className="info-icon" onClick={() => setShowInfo((v) => !v)} aria-label="How this works">
                <Info size={16} />
              </button>
              {showInfo && (
                <div className="info-popover">
                  <div className="info-popover-header">
                    How this works
                    <button type="button" className="icon-btn" onClick={() => setShowInfo(false)} aria-label="Close">
                      <X size={15} />
                    </button>
                  </div>
                  <p>
                    SupportAI classifies your message with a fine-tuned open-source LLM, looks up your order, checks the return and exchange rules, searches the policies, and either resolves it, asks a question, or hands you to a person.
                  </p>
                </div>
              )}
            </div>
            <p className="header-subtitle">
              <ShieldCheck size={13} /> Synthetic Demo Environment · Fictional customers and orders
            </p>
          </div>
          <a className="btn-outline sm header-link" href="#/orders">
            View orders
          </a>
          <button type="button" className="btn-outline sm header-link" onClick={() => send("I want to talk to a human agent.")} disabled={busy}>
            Talk to a human
          </button>
          <div className={`status-pill ${offline ? "offline" : health ? "online" : ""}`}>
            <span className="status-dot" />
            {offline ? "Waking up" : health ? "Online" : "Connecting"}
          </div>
          <button type="button" className="icon-btn rail-toggle" onClick={() => setRailOpen((v) => !v)} aria-label="Toggle AI details">
            <PanelRight size={20} />
          </button>
        </header>

        {offline && <div className="offline-banner">SupportAI is waking up. This may take up to 30 seconds.</div>}

        <div className="chat-body">
          <section className="chat-column">
            <div className="chat-scroll" ref={scrollRef}>
              {messages.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon">
                    <Bot size={26} />
                  </div>
                  <p className="empty-title">Hi! How can I help you today?</p>
                  <p className="empty-subtitle">I can help you track orders, return products, exchange sizes, check refunds and more.</p>
                  <div className="quick-grid">
                    {QUICK_ACTIONS.map(([label, text, Icon]) => (
                      <button key={label} type="button" className="quick-card" onClick={() => send(text)} disabled={!meta}>
                        <Icon size={18} /> {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => {
                if (m.role === "user") return <UserMessage key={m.id} message={m} />;
                if (m.error) return <ErrorMessage key={m.id} message={m} canRetry={i === messages.length - 1 && !busy} onRetry={() => retry(m)} />;
                return <AssistantMessage key={m.id} message={m} isLast={i === messages.length - 1} busy={busy} view={view} onHuman={() => send("I want to talk to a human agent.")} onChoose={handleChoose} onSelectSize={handleSelectSize} onFeedback={handleFeedback} />;
              })}
              {busy && <PendingMessage steps={activePending.steps} />}
            </div>

            <div className="composer">
              <textarea
                ref={textareaRef}
                rows={1}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Type your message here…"
                aria-label="Message"
              />
              <button type="button" onClick={() => sendTyped(draft)} disabled={busy || !draft.trim()} aria-label="Send">
                <Send size={18} />
              </button>
            </div>
          </section>

          <aside className={`rail ${railOpen ? "open" : ""}`}>
            <div className="view-toggle" role="group" aria-label="Panel view">
              <button type="button" aria-pressed={view === "customer"} className={view === "customer" ? "on" : ""} onClick={() => setView("customer")}>
                Customer View
              </button>
              <button type="button" aria-pressed={view === "diagnostics"} className={view === "diagnostics" ? "on" : ""} onClick={() => setView("diagnostics")}>
                AI Diagnostics
              </button>
            </div>
            {view === "customer" ? (
              <CustomerPanel result={lastResult} pending={busy} pendingSteps={activePending?.steps ?? []} onHuman={() => send("I want to talk to a human agent.")} busy={busy} onOpenPolicies={() => setOverlay({ tab: "policies" })} />
            ) : (
              <DecisionPanel onHuman={() => send("I want to talk to a human agent.")} busy={busy} result={lastResult} pending={busy} pendingSteps={activePending?.steps ?? []} onOpenPolicies={() => setOverlay({ tab: "policies" })} />
            )}
          </aside>
        </div>
      </main>

      {overlay && <InfoPanel tab={overlay.tab} highlight={overlay.highlight} meta={meta} onTab={(tab) => setOverlay({ tab })} onClose={() => setOverlay(null)} />}
    </div>
  );
}
