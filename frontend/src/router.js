import { useEffect, useState } from "react";

// Hash routing keeps deep links working on any static host (Vercel included)
// without server-side rewrites.
function parse() {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  return { path: path || "/", query: new URLSearchParams(query) };
}

export function useRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onChange = () => {
      setRoute(parse());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function href(path, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v == null || v === "" || (Array.isArray(v) && !v.length)) continue;
    if (Array.isArray(v)) v.forEach((x) => qs.append(k, x));
    else qs.set(k, v);
  }
  const s = qs.toString();
  return `#${path}${s ? `?${s}` : ""}`;
}

export const navigate = (path, params) => {
  window.location.hash = href(path, params).slice(1);
};
