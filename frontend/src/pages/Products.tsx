import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { formatPrice, getProducts, type ProductSummary } from "../api.ts";
import { useChatResults } from "../chatResults.tsx";
import { rememberProductsSearch } from "../navMemory.ts";
import { ProductTile, SIZES } from "../ui.tsx";

// Remember where the shopper was on this list, so "Back" from a product page returns to the same spot.
let scrollMemory: { key: number | "all" | null; y: number } = { key: null, y: 0 };

// ---- Filter bar (Problem 9) ------------------------------------------------
const CATEGORY_ORDER = ["t-shirt", "long-sleeve shirt", "crewneck", "hoodie", "full-zip hoodie", "quarter-zip", "jacket"];
type Sort = "name" | "price_asc" | "price_desc";

function applyFilters(products: ProductSummary[], q: string, cat: string, size: string, sort: Sort) {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const out = products.filter((p) => {
    if (cat && p.category !== cat) return false;
    if (size && !p.sizes_in_stock.includes(size)) return false;
    if (!words.length) return true;
    const text = `${p.name} ${p.description} ${p.colors.join(" ")} ${p.category}`.toLowerCase();
    return words.every((w) => text.includes(w.replace(/s$/, "")));
  });
  if (sort === "price_asc") out.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name));
  else if (sort === "price_desc") out.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name));
  return out;
}

function filterLabel(filters: Record<string, string | number>): string {
  const parts: string[] = [];
  if (filters.category) parts.push(String(filters.category));
  if (filters.color) parts.push(String(filters.color));
  if (filters.size) parts.push(`size ${filters.size} in stock`);
  if (filters.min_price) parts.push(`from ${formatPrice(Number(filters.min_price))}`);
  if (filters.max_price) parts.push(`up to ${formatPrice(Number(filters.max_price))}`);
  if (filters.sort === "price_asc") parts.push("cheapest first");
  if (filters.sort === "price_desc") parts.push("most expensive first");
  return parts.join(" · ");
}

export default function Products() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const { results, clearResults } = useChatResults();

  // Filters live in the URL (?q=&cat=&size=&sort=) so they survive Back from a product page and can be shared.
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const cat = params.get("cat") ?? "";
  const size = params.get("size") ?? "";
  const sort = (params.get("sort") as Sort) || "name";
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  useEffect(() => rememberProductsSearch(params.toString() ? `?${params.toString()}` : ""), [params]);
  const filtersActive = Boolean(q || cat || size || sort !== "name");
  const visible = useMemo(() => applyFilters(products, q, cat, size, sort), [products, q, cat, size, sort]);
  const categories = useMemo(
    () => CATEGORY_ORDER.filter((c) => products.some((p) => p.category === c)),
    [products],
  );

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch(() => setError("Couldn't load products. Is the backend running on port 8000?"))
      .finally(() => setLoading(false));
  }, []);

  // Scroll: restore the old position when coming back from a product page; jump to the top
  // when the chat has just delivered NEW results.
  const listKey = results ? results.receivedAt : "all";
  const waitingForGrid = !results && loading; // chat results render at once; the full grid loads async
  useEffect(() => {
    if (waitingForGrid) return;
    if (scrollMemory.key === listKey) window.scrollTo(0, scrollMemory.y);
    else if (results) window.scrollTo({ top: 0, behavior: "smooth" });
    return () => {
      scrollMemory = { key: listKey, y: window.scrollY };
    };
  }, [listKey, waitingForGrid]); // eslint-disable-line react-hooks/exhaustive-deps

  if (results) {
    const label = filterLabel(results.filters);
    return (
      <section className="section">
        <div className="chat-results-banner" key={results.receivedAt}>
          <div>
            <p className="section-num"><span className="pulse-dot" aria-hidden="true" /> Curated by your Concierge</p>
            <h1 className="display-sm">{results.heading}</h1>
            <p className="muted">
              {results.total_matches} match{results.total_matches === 1 ? "" : "es"}
              {results.query ? ` for “${results.query}”` : ""}
              {label ? ` · ${label}` : ""}
              {results.products.length < results.total_matches ? ` (showing ${results.products.length})` : ""}
            </p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={clearResults}>
            Show all products
          </button>
        </div>
        <div className="product-grid" key={`g${results.receivedAt}`}>
          {results.products.map((p, i) => (
            <ProductTile key={p.product_id} index={i} p={p} />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="section">
      <header className="shop-head">
        <p className="section-num">The Collection · {products.length || "…"} pieces</p>
        <h1 className="display">Everything <em>on the rack.</em></h1>
        <p className="lead">
          Tees, crewnecks, hoodies, quarter-zips and jackets, XS to XXL. Tip: ask the Concierge
          (bottom right) “what hoodies do you have?” and it'll curate this page for you.
        </p>
      </header>

      {loading && (
        <div className="product-grid" aria-label="Loading products">
          {Array.from({ length: 8 }, (_, i) => <div className="tile skeleton" key={i} />)}
        </div>
      )}
      {error && <div className="placeholder error">{error}</div>}

      {!loading && !error && (
        <>
          <div className="filter-panel">
          <div className="filter-bar" role="search">
            <input
              type="search"
              className="filter-search"
              placeholder="Search: e.g. bulldog, navy, Davenport…"
              value={q}
              onChange={(e) => setParam("q", e.target.value)}
              aria-label="Search products"
            />
            <select value={size} onChange={(e) => setParam("size", e.target.value)} aria-label="Size in stock">
              <option value="">Any size</option>
              {SIZES.map((s) => <option key={s} value={s}>In stock in {s}</option>)}
            </select>
            <select value={sort} onChange={(e) => setParam("sort", e.target.value)} aria-label="Sort">
              <option value="name">Sort: A–Z</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </select>
          </div>
          <div className="category-chips" role="group" aria-label="Category">
            <button type="button" className={`chip-btn${cat === "" ? " active" : ""}`} onClick={() => setParam("cat", "")}>
              All
            </button>
            {categories.map((c) => (
              <button
                type="button"
                key={c}
                className={`chip-btn${cat === c ? " active" : ""}`}
                onClick={() => setParam("cat", cat === c ? "" : c)}
              >
                {c}
              </button>
            ))}
          </div>
          </div>
          <p className="muted results-count">
            Showing {visible.length} of {products.length} products
            {filtersActive && (
              <button type="button" className="link-btn" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                Clear filters
              </button>
            )}
          </p>
          {visible.length === 0 && (
            <div className="placeholder">
              No products match these filters. Try clearing a filter, or ask the assistant (bottom right).
            </div>
          )}
          <div className="product-grid">
            {visible.map((p, i) => <ProductTile key={p.product_id} index={i} p={p} />)}
          </div>
        </>
      )}
    </section>
  );
}
