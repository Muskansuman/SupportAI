import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const KEY = "supportai_shop_v1";
const ShopContext = createContext(null);

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (saved) return { wishlist: saved.wishlist ?? [], bag: saved.bag ?? [] };
  } catch {
    // unreadable: start empty
  }
  return { wishlist: [], bag: [] };
}

// Wishlist and bag live in the browser: the demo has no accounts or checkout,
// so nothing here is sent to the server.
export function ShopProvider({ children }) {
  const [state, setState] = useState(load);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      // storage unavailable: works for this session only
    }
  }, [state]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  const toggleWishlist = useCallback((product) => {
    setState((s) => {
      const has = s.wishlist.some((p) => p.product_id === product.product_id);
      return { ...s, wishlist: has ? s.wishlist.filter((p) => p.product_id !== product.product_id) : [product, ...s.wishlist] };
    });
  }, []);

  const addToBag = useCallback((product, size) => {
    setState((s) => {
      const existing = s.bag.find((i) => i.product.product_id === product.product_id && i.size === size);
      const bag = existing
        ? s.bag.map((i) => (i === existing ? { ...i, qty: Math.min(i.qty + 1, 5) } : i))
        : [...s.bag, { product, size, qty: 1 }];
      return { ...s, bag };
    });
    setToast(`Added to bag · size ${size}`);
  }, []);

  const updateQty = useCallback((product_id, size, qty) => {
    setState((s) => ({ ...s, bag: s.bag.map((i) => (i.product.product_id === product_id && i.size === size ? { ...i, qty: Math.max(1, Math.min(5, qty)) } : i)) }));
  }, []);

  const removeFromBag = useCallback((product_id, size) => {
    setState((s) => ({ ...s, bag: s.bag.filter((i) => !(i.product.product_id === product_id && i.size === size)) }));
  }, []);

  const clearBag = useCallback(() => setState((s) => ({ ...s, bag: [] })), []);

  const value = useMemo(
    () => ({
      wishlist: state.wishlist,
      bag: state.bag,
      isWished: (id) => state.wishlist.some((p) => p.product_id === id),
      bagCount: state.bag.reduce((n, i) => n + i.qty, 0),
      toggleWishlist,
      addToBag,
      updateQty,
      removeFromBag,
      clearBag,
      toast,
      notify: setToast,
    }),
    [state, toggleWishlist, addToBag, updateQty, removeFromBag, clearBag, toast]
  );
  return <ShopContext.Provider value={value}>{children}</ShopContext.Provider>;
}

export const useShop = () => useContext(ShopContext);
