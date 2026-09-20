const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function networkError() {
  // fetch itself threw: the server is unreachable (down, cold-starting, CORS blocked)
  const err = new Error("SupportAI is unreachable right now.");
  err.isNetworkError = true;
  return err;
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw networkError();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      // response wasn't JSON: keep statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

const post = (path, body) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const getHealth = () => request("/health");
export const getMeta = () => request("/support/meta");
export const getScenarios = () => request("/support/scenarios");
export const getKnowledge = () => request("/support/knowledge");
export const getEvaluation = () => request("/support/evaluation");
export const resolve = (body) => post("/support/resolve", body);

// Reads the server-sent events stream: one `step` event as each pipeline
// stage really finishes, then `result`. Falls back to the plain endpoint if
// streaming isn't available (e.g. a proxy that buffers responses).
export async function resolveStream(body, onStep) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}/support/resolve/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw networkError();
  }
  if (!res.ok || !res.body) return resolve(body);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = /^event: (.+)$/m.exec(chunk)?.[1];
      const data = /^data: (.+)$/m.exec(chunk)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === "step") onStep(payload);
      else if (event === "result") result = payload;
      else if (event === "error") throw new Error(payload.detail);
    }
  }
  if (!result) return resolve(body);
  return result;
}

export const getFacets = () => request("/shop/facets");
export const getProduct = (id) => request(`/products/${encodeURIComponent(id)}`);
const owner = (c) => (c ? `customer_id=${encodeURIComponent(c)}` : "");
export const getOrder = (id, customer) => request(`/orders/${encodeURIComponent(id)}?${owner(customer)}`);
export const getTracking = (id, customer) => request(`/orders/${encodeURIComponent(id)}/tracking?${owner(customer)}`);
export const getEligibility = (id, customer) => request(`/orders/${encodeURIComponent(id)}/eligibility?${owner(customer)}`);
export const getCustomerOrders = (id, limit = 50) => request(`/customers/${encodeURIComponent(id)}/orders?limit=${limit}`);

// Repeated keys for list filters (category=a&category=b), which FastAPI expects.
export function getProducts(params = {}) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) continue;
    if (Array.isArray(value)) value.forEach((v) => qs.append(key, v));
    else qs.set(key, value);
  }
  return request(`/shop/products?${qs}`);
}
