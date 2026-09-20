import { useEffect, useRef, useState } from "react";
import { Heart, Home, LifeBuoy, LogOut, Package, Search, ShoppingBag, User } from "lucide-react";
import { navigate } from "../router";
import { useShop } from "./ShopContext";

const NAV = [
  ["Men", "/shop", { gender: "Men" }],
  ["Women", "/shop", { gender: "Women" }],
  ["Footwear", "/shop", { category: ["Sneakers", "Casual Shoes"] }],
  ["Offers", "/shop", { sort: "discount" }],
];

const q = (params) => new URLSearchParams(Object.entries(params).flatMap(([k, v]) => (Array.isArray(v) ? v.map((x) => [k, x]) : [[k, v]]))).toString();

function Badge({ n }) {
  return n > 0 ? <span className="nav-badge">{n > 9 ? "9+" : n}</span> : null;
}

export default function Header({ customer, path, search, onLogout }) {
  const { wishlist, bagCount } = useShop();
  const [text, setText] = useState(search);
  const [lastSearch, setLastSearch] = useState(search);
  // The box mirrors the URL: leaving a search page clears it.
  if (search !== lastSearch) {
    setLastSearch(search);
    setText(search);
  }
  const [menu, setMenu] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menu) return;
    const close = (e) => menuRef.current && !menuRef.current.contains(e.target) && setMenu(false);
    const esc = (e) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [menu]);

  function submit(e) {
    e.preventDefault();
    navigate("/shop", text.trim() ? { q: text.trim() } : {});
  }

  const go = (to) => {
    setMenu(false);
    navigate(to);
  };

  return (
    <>
      <header className="shop-header">
        <a className="brand" href="#/" aria-label="SupportAI home">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <span className="brand-text">
            <strong>SupportAI</strong>
            <small>AI Shopping Assistant</small>
          </span>
        </a>

        <nav className="shop-nav" aria-label="Categories">
          {NAV.map(([label, to, params]) => (
            <a key={label} href={`#${to}?${q(params)}`}>
              {label}
            </a>
          ))}
        </nav>

        <form className="search-box" role="search" onSubmit={submit}>
          <Search size={17} aria-hidden="true" />
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Search for products, brands and more" aria-label="Search products" />
        </form>

        <div className="header-actions">
          <div className="profile-wrap" ref={menuRef}>
            <button type="button" className="action-btn" onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu}>
              <span className="avatar-dot">
                <User size={19} />
                <i className="online-dot" />
              </span>
              <span className="action-label">Profile</span>
            </button>
            {menu && (
              <div className="profile-menu" role="menu">
                <div className="profile-head">
                  <div className="profile-name">{customer?.name ?? "Demo customer"}</div>
                  <div className="profile-email">{customer?.email ?? "demo.customer@example.com"}</div>
                  <div className="profile-id">{customer?.customer_id}</div>
                  <div className="profile-status">
                    <i className="online-dot" /> Logged in · {customer?.city}
                    {customer?.tier === "premium" ? " · Premium" : ""}
                  </div>
                </div>
                <button type="button" role="menuitem" onClick={() => go("/orders")}>
                  <Package size={16} /> My Orders
                </button>
                <button type="button" role="menuitem" onClick={() => go("/wishlist")}>
                  <Heart size={16} /> Wishlist
                </button>
                <button type="button" role="menuitem" onClick={() => go("/support")}>
                  <LifeBuoy size={16} /> Help Center
                </button>
                <button type="button" role="menuitem" className="danger" onClick={onLogout}>
                  <LogOut size={16} /> Reset demo session
                </button>
                <div className="profile-note">Synthetic Demo Environment. Resetting clears your local wishlist, bag and chats.</div>
              </div>
            )}
          </div>
          <a className="action-btn" href="#/orders">
            <Package size={20} />
            <span className="action-label">Orders</span>
          </a>
          <a className="action-btn" href="#/wishlist">
            <span className="icon-wrap">
              <Heart size={20} />
              <Badge n={wishlist.length} />
            </span>
            <span className="action-label">Wishlist</span>
          </a>
          <a className="action-btn" href="#/bag">
            <span className="icon-wrap">
              <ShoppingBag size={20} />
              <Badge n={bagCount} />
            </span>
            <span className="action-label">Bag</span>
          </a>
          <a className={`help-btn ${path === "/support" ? "active" : ""}`} href="#/support">
            <LifeBuoy size={16} /> Get help
          </a>
        </div>
      </header>

      <nav className="bottom-nav" aria-label="Main">
        {[
          ["/", "Home", Home],
          ["/shop", "Search", Search],
          ["/orders", "Orders", Package],
          ["/support", "Support", LifeBuoy],
          ["/bag", "Bag", ShoppingBag],
        ].map(([to, label, Icon]) => (
          <a key={to} href={`#${to}`} className={path === to || (to !== "/" && path.startsWith(to)) ? "active" : ""}>
            <span className="icon-wrap">
              <Icon size={21} />
              {to === "/bag" && <Badge n={bagCount} />}
            </span>
            {label}
          </a>
        ))}
      </nav>
    </>
  );
}
