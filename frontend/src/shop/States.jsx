import { AlertCircle } from "lucide-react";

export function GridSkeleton({ n = 8 }) {
  return (
    <div className="product-grid" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="product-card skeleton-card">
          <div className="skeleton media" />
          <div className="skeleton line" />
          <div className="skeleton line short" />
        </div>
      ))}
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="state-box error" role="alert">
      <AlertCircle size={22} />
      <p>{message?.includes("unreachable") ? "The SupportAI backend can't be reached right now. It may be starting up." : message}</p>
      {onRetry && (
        <button type="button" className="btn-outline" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="state-box">
      {Icon && <Icon size={34} />}
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}
