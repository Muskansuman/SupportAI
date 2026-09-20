import { useEffect, useState } from "react";
import { Heart, LifeBuoy, PackageX, RefreshCw, Truck, Undo2 } from "lucide-react";
import { getProduct } from "../api";
import { navigate } from "../router";
import ProductImage from "../shop/ProductImage";
import { EmptyState, ErrorBox } from "../shop/States";
import { useShop } from "../shop/ShopContext";
import { money } from "../utils";

export default function Product({ id, meta }) {
  const { addToBag, isWished, toggleWishlist } = useShop();
  const [state, setState] = useState({ loading: true });
  const [size, setSize] = useState(null);
  const [needSize, setNeedSize] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    setSize(null);
    setNeedSize(false);
    getProduct(id)
      .then((p) => !cancelled && setState({ product: p }))
      .catch((e) => !cancelled && setState({ error: e.message, notFound: /not found/i.test(e.message) }));
    return () => {
      cancelled = true;
    };
  }, [id, attempt]);

  if (state.loading) return <div className="page"><div className="skeleton detail-skeleton" aria-busy="true" /></div>;
  if (state.notFound)
    return (
      <div className="page">
        <EmptyState icon={PackageX} title="Product not found" text={`We couldn't find a product with the ID ${id}.`} action={<a className="btn-outline" href="#/shop">Browse products</a>} />
      </div>
    );
  if (state.error) return <div className="page"><ErrorBox message={state.error} onRetry={() => setAttempt((n) => n + 1)} /></div>;

  const p = state.product;
  const w = meta?.policy_windows;
  const wished = isWished(p.product_id);
  const stockOf = (s) => p.stock_by_size?.[s] ?? 0;
  const anyStock = p.sizes.some((s) => stockOf(s) > 0);
  const compact = { ...p, in_stock_sizes: p.sizes.filter((s) => stockOf(s) > 0) };

  function requireSize() {
    if (!size) {
      setNeedSize(true);
      return false;
    }
    return true;
  }

  return (
    <div className="page product-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/">Home</a> / <a href={`#/shop?gender=${p.gender === "Unisex" ? "" : p.gender}`}>{p.gender}</a> / <a href={`#/shop?category=${encodeURIComponent(p.category)}`}>{p.category}</a>
      </nav>

      <div className="product-detail">
        <div className="detail-media">
          <ProductImage product={p} large />
        </div>

        <div className="detail-info">
          <div className="detail-brand">{p.brand}</div>
          <h1>{p.name.replace(p.brand, "").trim()}</h1>
          <div className="detail-prices">
            <strong>{money(p.price)}</strong>
            {p.discount_pct > 0 && (
              <>
                <s>MRP {money(p.mrp)}</s>
                <span className="product-off">({p.discount_pct}% OFF)</span>
              </>
            )}
          </div>
          <div className="tax-note">Inclusive of all taxes</div>

          <div className="detail-color">
            Colour: <strong>{p.color}</strong>
          </div>

          <div className="size-head">
            <strong>Select size</strong>
            {needSize && <span className="size-error" role="alert">Please select a size</span>}
          </div>
          <div className="size-options" role="radiogroup" aria-label="Size">
            {p.sizes.map((s) => {
              const left = stockOf(s);
              return (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={size === s}
                  disabled={left === 0}
                  className={`size-pill ${size === s ? "selected" : ""}`}
                  onClick={() => {
                    setSize(s);
                    setNeedSize(false);
                  }}
                  title={left === 0 ? "Out of stock" : left <= 3 ? `Only ${left} left` : "In stock"}
                >
                  {s}
                  {left > 0 && left <= 3 && <small>{left} left</small>}
                </button>
              );
            })}
          </div>

          <div className="detail-actions">
            <button type="button" className="btn-solid" disabled={!anyStock} onClick={() => requireSize() && addToBag(compact, size)}>
              {anyStock ? "Add to bag" : "Sold out"}
            </button>
            <button type="button" className="btn-outline" disabled={!anyStock} onClick={() => requireSize() && (addToBag(compact, size), navigate("/bag"))}>
              Buy now
            </button>
            <button type="button" className={`btn-outline wish ${wished ? "on" : ""}`} onClick={() => toggleWishlist(compact)} aria-pressed={wished}>
              <Heart size={16} fill={wished ? "currentColor" : "none"} /> {wished ? "Wishlisted" : "Wishlist"}
            </button>
          </div>

          <ul className="assurances">
            <li>
              <Truck size={18} /> Free delivery
            </li>
            <li>
              <Undo2 size={18} /> {p.returnable ? `${w?.return_days ?? 14}-day returns` : "Not returnable"}
            </li>
            <li>
              <RefreshCw size={18} /> {p.exchangeable ? `${w?.exchange_days ?? 10}-day size exchange` : "Not exchangeable"}
            </li>
          </ul>

          <div className="help-callout">
            <div>
              <strong>Need help with this product?</strong>
              <span>Ask about sizing, delivery, returns or exchanges.</span>
            </div>
            <a className="btn-outline" href={`#/support?product=${p.product_id}`}>
              <LifeBuoy size={16} /> Ask SupportAI
            </a>
          </div>

          <section className="detail-specs">
            <h2>Product details</h2>
            <dl>
              <dt>Brand</dt>
              <dd>{p.brand}</dd>
              <dt>Category</dt>
              <dd>{p.category}</dd>
              <dt>For</dt>
              <dd>{p.gender}</dd>
              <dt>Fit / pattern</dt>
              <dd>{p.fit}</dd>
              <dt>Colour</dt>
              <dd>{p.color}</dd>
              <dt>Product ID</dt>
              <dd>{p.product_id}</dd>
            </dl>
            <p className="synthetic-note">Illustration shown instead of a photo. This is a synthetic demo product.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
