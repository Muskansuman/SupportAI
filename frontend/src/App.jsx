import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { getHealth, getMeta, getProduct } from "./api";
import { useRoute } from "./router";
import Header from "./shop/Header";
import { ShopProvider, useShop } from "./shop/ShopContext";
import { EmptyState } from "./shop/States";
import Bag from "./pages/Bag";
import Home from "./pages/Home";
import OrderDetail from "./pages/OrderDetail";
import Orders from "./pages/Orders";
import Product from "./pages/Product";
import Shop from "./pages/Shop";
import Support from "./pages/Support";
import Wishlist from "./pages/Wishlist";
import "./App.css";
import "./shop.css";

const SESSION_KEYS = ["supportai_shop_v1", "supportai_fashion_v1"];

function Toast() {
  const { toast } = useShop();
  return toast ? (
    <div className="toast" role="status">
      {toast}
    </div>
  ) : null;
}

function Routes({ route, meta, health, healthError }) {
  const { path, query } = route;
  const customerId = meta?.demo_customer?.customer_id;
  const [productContext, setProductContext] = useState(null);

  // "Ask SupportAI" on a product page passes the product ID; resolve its name.
  const productId = path === "/support" ? query.get("product") : null;
  useEffect(() => {
    if (!productId) return;
    getProduct(productId)
      .then((p) => setProductContext({ productName: p.name, key: productId }))
      .catch(() => setProductContext(null));
  }, [productId]);

  if (path === "/") return <Home meta={meta} />;
  if (path === "/shop") return <Shop query={query} />;
  if (path.startsWith("/product/")) return <Product id={decodeURIComponent(path.slice(9))} meta={meta} />;
  if (path === "/wishlist") return <Wishlist />;
  if (path === "/bag") return <Bag />;
  if (path === "/orders") return <Orders customerId={customerId} />;
  if (path.startsWith("/orders/")) return <OrderDetail id={decodeURIComponent(path.slice(8))} customerId={customerId} demoNow={meta?.demo_clock} />;
  if (path === "/support") {
    const order = query.get("order");
    const context = order ? { order, topic: query.get("topic") } : productContext;
    return <Support meta={meta} health={health} healthError={healthError} context={context} />;
  }
  return (
    <div className="page">
      <EmptyState title="Page not found" text="That page doesn't exist." action={<a className="btn-solid" href="#/">Go home</a>} />
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [meta, setMeta] = useState(null);

  // Retries every 5s until the backend answers, so a cold-starting server
  // isn't reported as offline forever after one failed check.
  useEffect(() => {
    let cancelled = false;
    function poll() {
      getHealth()
        .then((data) => {
          if (cancelled) return;
          setHealth(data);
          setHealthError(null);
          getMeta().then((m) => !cancelled && setMeta(m)).catch(() => {});
        })
        .catch((e) => {
          if (cancelled) return;
          setHealthError(e.message);
          setTimeout(poll, 5000);
        });
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  function resetSession() {
    try {
      SESSION_KEYS.forEach((k) => localStorage.removeItem(k));
    } catch {
      // storage unavailable: nothing to clear
    }
    window.location.hash = "#/";
    window.location.reload();
  }

  const onSupport = route.path === "/support";
  return (
    <ShopProvider>
      <div className={`shop-shell ${onSupport ? "support-mode" : ""}`}>
        <Header customer={meta?.demo_customer} path={route.path} search={route.path === "/shop" ? (route.query.get("q") ?? "") : ""} onLogout={resetSession} />
        {healthError && !health && !onSupport && <div className="offline-banner">SupportAI is waking up. This may take up to 30 seconds.</div>}
        <main className="shop-main">
          <Routes route={route} meta={meta} health={health} healthError={healthError} />
        </main>
        {!onSupport && (
          <footer className="shop-footer">
            <ShieldCheck size={16} />
            <span>
              <strong>Synthetic Demo Environment.</strong> All customer, product and order information shown here is synthetic data created for demonstration purposes. Not affiliated with any retailer.
            </span>
          </footer>
        )}
        <Toast />
      </div>
    </ShopProvider>
  );
}
