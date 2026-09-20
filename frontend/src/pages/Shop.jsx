import { useEffect, useState } from "react";
import { SearchX, SlidersHorizontal, X } from "lucide-react";
import { getFacets, getProducts } from "../api";
import { href } from "../router";
import ProductCard from "../shop/ProductCard";
import { EmptyState, ErrorBox, GridSkeleton } from "../shop/States";

const PAGE = 24;
const SORTS = [
  ["relevance", "Recommended"],
  ["popular", "Most ordered"],
  ["discount", "Better discount"],
  ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"],
];
const PRICE_BANDS = [
  ["Under ₹500", null, 500],
  ["₹500 – ₹1,000", 500, 1000],
  ["₹1,000 – ₹2,000", 1000, 2000],
  ["Above ₹2,000", 2000, null],
];

function readFilters(query) {
  return {
    q: query.get("q") ?? "",
    gender: query.get("gender") ?? "",
    category: query.getAll("category"),
    brand: query.getAll("brand"),
    color: query.getAll("color"),
    size: query.getAll("size"),
    min_price: query.get("min_price") ?? "",
    max_price: query.get("max_price") ?? "",
    sort: query.get("sort") ?? "relevance",
  };
}

function CheckGroup({ title, options, selected, onToggle, limit = 8 }) {
  const [all, setAll] = useState(false);
  const shown = all ? options : options.slice(0, limit);
  return (
    <fieldset className="filter-group">
      <legend>{title}</legend>
      {shown.map((o) => (
        <label key={o.value}>
          <input type="checkbox" checked={selected.includes(o.value)} onChange={() => onToggle(o.value)} />
          <span>{o.value}</span>
          {o.count != null && <small>{o.count}</small>}
        </label>
      ))}
      {options.length > limit && (
        <button type="button" className="link-btn" onClick={() => setAll((v) => !v)}>
          {all ? "Show less" : `Show all ${options.length}`}
        </button>
      )}
    </fieldset>
  );
}

export default function Shop({ query }) {
  const f = readFilters(query);
  const key = query.toString();
  const [facets, setFacets] = useState(null);
  const [state, setState] = useState({ loading: true });
  const [extra, setExtra] = useState([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    setExtra([]);
    getProducts({ ...f, limit: PAGE })
      .then((d) => !cancelled && setState({ items: d.items, total: d.total }))
      .catch((e) => !cancelled && setState({ error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [key, attempt]);

  const update = (patch) => {
    window.location.hash = href("/shop", { ...f, ...patch }).slice(1);
  };
  const toggle = (field) => (value) => update({ [field]: f[field].includes(value) ? f[field].filter((v) => v !== value) : [...f[field], value] });

  async function loadMore() {
    setLoadingMore(true);
    try {
      const d = await getProducts({ ...f, limit: PAGE, offset: PAGE + extra.length });
      setExtra((prev) => [...prev, ...d.items]);
    } catch {
      // leave the button in place so the shopper can retry
    } finally {
      setLoadingMore(false);
    }
  }

  const items = state.items ? [...state.items, ...extra] : [];
  const activeChips = [
    ...(f.gender ? [["gender", f.gender]] : []),
    ...f.category.map((v) => ["category", v]),
    ...f.brand.map((v) => ["brand", v]),
    ...f.color.map((v) => ["color", v]),
    ...f.size.map((v) => ["size", `Size ${v}`, v]),
    ...(f.min_price || f.max_price ? [["price", `₹${f.min_price || 0} – ${f.max_price ? "₹" + f.max_price : "any"}`]] : []),
  ];
  const chipRemove = (chip) => {
    const [field, label, value] = chip;
    if (field === "gender") return update({ gender: "" });
    if (field === "price") return update({ min_price: "", max_price: "" });
    update({ [field]: f[field].filter((v) => v !== (value ?? label)) });
  };

  const filters = facets && (
    <div className="filters">
      <fieldset className="filter-group">
        <legend>Gender</legend>
        {["Men", "Women"].map((g) => (
          <label key={g}>
            <input type="radio" name="gender" checked={f.gender === g} onChange={() => update({ gender: g })} />
            <span>{g}</span>
          </label>
        ))}
        {f.gender && (
          <button type="button" className="link-btn" onClick={() => update({ gender: "" })}>
            Clear
          </button>
        )}
      </fieldset>
      <CheckGroup title="Category" options={facets.categories} selected={f.category} onToggle={toggle("category")} />
      <CheckGroup title="Brand" options={facets.brands} selected={f.brand} onToggle={toggle("brand")} limit={6} />
      <fieldset className="filter-group">
        <legend>Price</legend>
        {PRICE_BANDS.map(([label, min, max]) => (
          <label key={label}>
            <input type="radio" name="price" checked={String(min ?? "") === f.min_price && String(max ?? "") === f.max_price} onChange={() => update({ min_price: min ?? "", max_price: max ?? "" })} />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>
      <CheckGroup title="Size" options={facets.sizes} selected={f.size} onToggle={toggle("size")} limit={20} />
      <CheckGroup title="Colour" options={facets.colors} selected={f.color} onToggle={toggle("color")} />
    </div>
  );

  return (
    <div className="page shop-page">
      <div className="listing-head">
        <div>
          <h1>{f.q ? `Results for “${f.q}”` : f.gender ? `${f.gender}'s clothing & footwear` : "All products"}</h1>
          {state.items && <p>{state.total.toLocaleString("en-IN")} products</p>}
        </div>
        <div className="listing-tools">
          <button type="button" className="btn-outline filters-toggle" onClick={() => setDrawer(true)}>
            <SlidersHorizontal size={16} /> Filters
          </button>
          <label className="sort-select">
            Sort by
            <select value={f.sort} onChange={(e) => update({ sort: e.target.value })}>
              {SORTS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {activeChips.length > 0 && (
        <div className="chip-row">
          {activeChips.map((chip) => (
            <button key={chip.join("|")} type="button" className="filter-chip" onClick={() => chipRemove(chip)}>
              {chip[1]} <X size={13} />
            </button>
          ))}
          <button type="button" className="link-btn" onClick={() => (window.location.hash = href("/shop", { q: f.q }).slice(1))}>
            Clear all
          </button>
        </div>
      )}

      <div className="listing">
        <aside className="filter-side">{filters}</aside>
        <div className="listing-main">
          {state.loading && <GridSkeleton />}
          {state.error && <ErrorBox message={state.error} onRetry={() => setAttempt((n) => n + 1)} />}
          {state.items && items.length === 0 && (
            <EmptyState icon={SearchX} title="No products found" text="Try a different search or remove some filters." action={<a className="btn-outline" href="#/shop">Browse all products</a>} />
          )}
          {state.items && items.length > 0 && (
            <>
              <div className="product-grid">{items.map((p) => <ProductCard key={p.product_id} product={p} />)}</div>
              {items.length < state.total && (
                <div className="load-more">
                  <button type="button" className="btn-outline" onClick={loadMore} disabled={loadingMore}>
                    {loadingMore ? "Loading…" : `Load more (${items.length} of ${state.total})`}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {drawer && (
        <div className="drawer-backdrop" onClick={() => setDrawer(false)}>
          <div className="filter-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Filters">
            <div className="drawer-head">
              <strong>Filters</strong>
              <button type="button" className="icon-btn" onClick={() => setDrawer(false)} aria-label="Close filters">
                <X size={18} />
              </button>
            </div>
            <div className="drawer-body">{filters}</div>
            <div className="drawer-foot">
              <button type="button" className="btn-solid" onClick={() => setDrawer(false)}>
                Show {state.total ?? ""} results
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
