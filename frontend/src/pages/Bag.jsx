import { useState } from "react";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import ProductImage from "../shop/ProductImage";
import { EmptyState } from "../shop/States";
import { useShop } from "../shop/ShopContext";
import { money } from "../utils";

export default function Bag() {
  const { bag, updateQty, removeFromBag, clearBag } = useShop();
  const [checkedOut, setCheckedOut] = useState(false);

  if (checkedOut)
    return (
      <div className="page">
        <EmptyState
          icon={ShoppingBag}
          title="Demo checkout complete"
          text="No order was created and no payment was taken. This is a synthetic demo, so the bag is simply cleared. To try support flows, use the sample orders under My Orders."
          action={
            <div className="state-actions">
              <a className="btn-solid" href="#/orders">View my orders</a>
              <a className="btn-outline" href="#/shop">Continue shopping</a>
            </div>
          }
        />
      </div>
    );

  if (bag.length === 0)
    return (
      <div className="page">
        <EmptyState icon={ShoppingBag} title="Your bag is empty" text="Add something you like and it will show up here." action={<a className="btn-solid" href="#/shop">Continue shopping</a>} />
      </div>
    );

  const mrp = bag.reduce((n, i) => n + i.product.mrp * i.qty, 0);
  const total = bag.reduce((n, i) => n + i.product.price * i.qty, 0);

  return (
    <div className="page">
      <div className="listing-head">
        <div>
          <h1>Shopping bag</h1>
          <p>{bag.length} {bag.length === 1 ? "item" : "items"}</p>
        </div>
      </div>
      <div className="bag-layout">
        <ul className="bag-list">
          {bag.map((i) => (
            <li key={`${i.product.product_id}-${i.size}`} className="bag-item">
              <a className="bag-thumb" href={`#/product/${i.product.product_id}`}>
                <ProductImage product={i.product} />
              </a>
              <div className="bag-info">
                <div className="product-brand">{i.product.brand}</div>
                <a href={`#/product/${i.product.product_id}`} className="bag-name">
                  {i.product.name.replace(i.product.brand, "").trim()}
                </a>
                <div className="bag-meta">Size {i.size} · {i.product.color}</div>
                <div className="qty">
                  <button type="button" onClick={() => updateQty(i.product.product_id, i.size, i.qty - 1)} disabled={i.qty <= 1} aria-label="Decrease quantity">
                    <Minus size={14} />
                  </button>
                  <span aria-live="polite">{i.qty}</span>
                  <button type="button" onClick={() => updateQty(i.product.product_id, i.size, i.qty + 1)} disabled={i.qty >= 5} aria-label="Increase quantity">
                    <Plus size={14} />
                  </button>
                </div>
              </div>
              <div className="bag-price">
                <strong>{money(i.product.price * i.qty)}</strong>
                {i.product.mrp > i.product.price && <s>{money(i.product.mrp * i.qty)}</s>}
                <button type="button" className="icon-btn" onClick={() => removeFromBag(i.product.product_id, i.size)} aria-label={`Remove ${i.product.name}`}>
                  <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>

        <aside className="bag-summary">
          <h2>Price details</h2>
          <dl>
            <dt>Total MRP</dt>
            <dd>{money(mrp)}</dd>
            <dt>Discount</dt>
            <dd className="good">− {money(mrp - total)}</dd>
            <dt>Delivery</dt>
            <dd className="good">FREE</dd>
          </dl>
          <div className="bag-total">
            <span>Total</span>
            <strong>{money(total)}</strong>
          </div>
          <a className="btn-outline block" href="#/shop">Continue shopping</a>
          <button
            type="button"
            className="btn-solid block"
            onClick={() => {
              clearBag();
              setCheckedOut(true);
            }}
          >
            Proceed to checkout
          </button>
          <p className="synthetic-note">Demo checkout: no payment is taken and no order is created.</p>
        </aside>
      </div>
    </div>
  );
}
