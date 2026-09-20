import { Heart } from "lucide-react";
import { money } from "../utils";
import { useShop } from "./ShopContext";
import ProductImage from "./ProductImage";

export default function ProductCard({ product }) {
  const { isWished, toggleWishlist } = useShop();
  const wished = isWished(product.product_id);
  const soldOut = product.in_stock_sizes.length === 0;

  return (
    <article className="product-card">
      <a className="product-link" href={`#/product/${product.product_id}`} aria-label={`${product.name}, ${money(product.price)}`}>
        <div className="product-media">
          <ProductImage product={product} />
          {soldOut && <span className="sold-out">Sold out</span>}
        </div>
        <div className="product-info">
          <div className="product-brand">{product.brand}</div>
          <div className="product-name">{product.name.replace(product.brand, "").trim()}</div>
          <div className="product-prices">
            <strong>{money(product.price)}</strong>
            {product.discount_pct > 0 && (
              <>
                <s>{money(product.mrp)}</s>
                <span className="product-off">{product.discount_pct}% OFF</span>
              </>
            )}
          </div>
          <div className="product-sizes">{product.in_stock_sizes.length ? `Sizes: ${product.in_stock_sizes.join(", ")}` : "Currently unavailable"}</div>
        </div>
      </a>
      <button type="button" className={`wish-btn ${wished ? "on" : ""}`} onClick={() => toggleWishlist(product)} aria-pressed={wished} aria-label={wished ? "Remove from wishlist" : "Add to wishlist"}>
        <Heart size={17} fill={wished ? "currentColor" : "none"} />
      </button>
    </article>
  );
}
