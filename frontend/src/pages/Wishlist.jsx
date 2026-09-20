import { Heart } from "lucide-react";
import ProductCard from "../shop/ProductCard";
import { EmptyState } from "../shop/States";
import { useShop } from "../shop/ShopContext";

export default function Wishlist() {
  const { wishlist } = useShop();
  return (
    <div className="page">
      <div className="listing-head">
        <div>
          <h1>My wishlist</h1>
          <p>{wishlist.length} {wishlist.length === 1 ? "item" : "items"}</p>
        </div>
      </div>
      {wishlist.length === 0 ? (
        <EmptyState icon={Heart} title="Your wishlist is empty" text="Tap the heart on any product to save it here." action={<a className="btn-solid" href="#/shop">Start shopping</a>} />
      ) : (
        <div className="product-grid">{wishlist.map((p) => <ProductCard key={p.product_id} product={p} />)}</div>
      )}
    </div>
  );
}
