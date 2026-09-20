import { useEffect, useState } from "react";
import { ArrowRight, LifeBuoy, RefreshCw, Truck, Undo2 } from "lucide-react";
import { getFacets, getProducts } from "../api";
import ProductCard from "../shop/ProductCard";
import { ErrorBox, GridSkeleton } from "../shop/States";

function Row({ title, subtitle, params, to }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let cancelled = false;
    getProducts({ ...params, limit: 8 })
      .then((d) => !cancelled && setState({ items: d.items }))
      .catch((e) => !cancelled && setState({ error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [JSON.stringify(params)]);

  return (
    <section className="home-section">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <a className="see-all" href={to}>
          See all <ArrowRight size={15} />
        </a>
      </div>
      {state.loading && <GridSkeleton n={4} />}
      {state.error && <ErrorBox message={state.error} />}
      {state.items && <div className="product-grid">{state.items.map((p) => <ProductCard key={p.product_id} product={p} />)}</div>}
    </section>
  );
}

export default function Home({ meta }) {
  const [facets, setFacets] = useState(null);
  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);
  const w = meta?.policy_windows;

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-eyebrow">Fashion · Footwear · Everyday wear</span>
          <h1>Shop smarter with SupportAI</h1>
          <p>Your AI-powered shopping and customer-support assistant. Track, return or exchange an order in a single conversation.</p>
          <div className="hero-actions">
            <a className="btn-solid" href="#/shop">
              Shop now
            </a>
            <a className="btn-outline" href="#/support">
              <LifeBuoy size={16} /> Get help
            </a>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <span className="blob b1" />
          <span className="blob b2" />
          <span className="blob b3" />
        </div>
      </section>

      <section className="promise-strip" aria-label="Store policies">
        <div>
          <Truck size={20} /> <span>Free delivery <small>on every demo order</small></span>
        </div>
        <div>
          <Undo2 size={20} /> <span>{w ? `${w.return_days}-day returns` : "Easy returns"} <small>on eligible items</small></span>
        </div>
        <div>
          <RefreshCw size={20} /> <span>{w ? `${w.exchange_days}-day exchanges` : "Size exchanges"} <small>subject to stock</small></span>
        </div>
        <div>
          <LifeBuoy size={20} /> <span>AI support <small>with human hand-off</small></span>
        </div>
      </section>

      {facets && (
        <section className="home-section">
          <div className="section-head">
            <div>
              <h2>Shop by category</h2>
              <p>{facets.total.toLocaleString("en-IN")} products across {facets.categories.length} categories</p>
            </div>
          </div>
          <div className="category-tiles">
            {facets.categories.map((c) => (
              <a key={c.value} href={`#/shop?category=${encodeURIComponent(c.value)}`} className="category-tile">
                <strong>{c.value}</strong>
                <small>{c.count} styles</small>
              </a>
            ))}
          </div>
        </section>
      )}

      <Row title="Trending now" subtitle="Ranked by how many orders each product has in the dataset" params={{ sort: "popular" }} to="#/shop?sort=popular" />
      <Row title="Best deals" subtitle="Biggest discounts first" params={{ sort: "discount" }} to="#/shop?sort=discount" />
    </div>
  );
}
