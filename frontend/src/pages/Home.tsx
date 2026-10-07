import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { formatPrice, getProducts, type ProductSummary } from "../api.ts";
import { Crest, ProductTile, displayName, openConcierge } from "../ui.tsx";

// Hero "hang tag" collage + editorial picks. Names, prices and images always come from the API.
const HERO_IDS = ["basic-hoodie-big-yale", "davenport-college-crewneck", "2025-yale-vs-harvard-t-shirt"];
const PICK_IDS = ["district-vit-hoodie-vintage-bulldog", "benjamin-franklin-fleece-jacket", "morse-1-4-zip", "boola-boola-t-shirt"];

const COLLECTION: { cat: string; title: string; line: string }[] = [
  { cat: "hoodie", title: "Hoodies", line: "Heavyweight fleece for the walk across Old Campus." },
  { cat: "crewneck", title: "Crewnecks", line: "College crests, varsity marks, vintage bulldogs." },
  { cat: "t-shirt", title: "Tees", line: "Everyday cotton, rivalry graphics, Big YALE." },
  { cat: "quarter-zip", title: "Quarter-Zips", line: "For the library, the lecture hall, the dinner after." },
  { cat: "jacket", title: "Jackets", line: "Fleece and bomber outerwear for New Haven winters." },
  { cat: "long-sleeve shirt", title: "Long Sleeves", line: "Lightweight performance layers." },
];

export default function Home() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  useEffect(() => {
    getProducts().then(setProducts).catch(() => setProducts([]));
  }, []);

  const byId = useMemo(() => new Map(products.map((p) => [p.product_id, p])), [products]);
  const hero = HERO_IDS.map((id) => byId.get(id)).filter((p): p is ProductSummary => Boolean(p));
  const picks = PICK_IDS.map((id) => byId.get(id)).filter((p): p is ProductSummary => Boolean(p));
  const rivalry = byId.get("2025-yale-vs-harvard-t-shirt");
  const categories = useMemo(
    () =>
      COLLECTION.map((c) => {
        const items = products.filter((p) => p.category === c.cat);
        return { ...c, count: items.length, image: items[0]?.image_url, from: Math.min(...items.map((p) => p.price)) };
      }).filter((c) => c.count > 0),
    [products],
  );
  const inStockUnits = products.filter((p) => p.in_stock).length;

  return (
    <>
      {/* ---------------- Hero ---------------- */}
      <section className="hero">
        <div className="hero-grain" aria-hidden="true" />
        <div className="hero-inner">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="eyebrow-rule" /> No. 57 Broadway · New Haven, Connecticut
            </p>
            <h1 className="display">
              Dressed for <em>the Elm City.</em>
            </h1>
            <p className="lead">
              Officially licensed Yale apparel, chosen for students, alumni, parents and every fan
              in the stands. Heavyweight fleece, college crests and game-day classics, from the
              shop around the corner.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-lg">Shop the collection</Link>
              <button type="button" className="btn btn-ghost btn-lg" onClick={() => openConcierge()}>
                <span className="pulse-dot" aria-hidden="true" /> Ask the Concierge
              </button>
            </div>
          </div>

          <div className="hero-collage" aria-label="Featured pieces">
            {hero.map((p, i) => (
              <Link to={`/products/${p.product_id}`} key={p.product_id} className={`hang hang-${i + 1}`}>
                <span className="hang-string" aria-hidden="true" />
                <img src={p.image_url} alt={displayName(p.name)} />
                <span className="hang-label">
                  <span>{displayName(p.name)}</span>
                  <strong>{formatPrice(p.price).replace(".00", "")}</strong>
                </span>
              </Link>
            ))}
            <Crest size={92} className="hero-seal" />
          </div>
        </div>

        <dl className="hero-stats">
          <div><dt>{products.length || "100+"}</dt><dd>styles on the rack</dd></div>
          <div><dt>{categories.length || 7}</dt><dd>silhouettes</dd></div>
          <div><dt>XS–XXL</dt><dd>stocked by size</dd></div>
          <div><dt>{inStockUnits || "—"}</dt><dd>pieces ready today</dd></div>
        </dl>
      </section>

      {/* ---------------- Collection ---------------- */}
      <section className="section">
        <header className="section-head" data-reveal>
          <p className="section-num">01 — The Collection</p>
          <h2 className="display-sm">Shop by <em>silhouette</em></h2>
        </header>
        <div className="collection">
          {categories.map((c, i) => (
            <Link to={`/products?cat=${encodeURIComponent(c.cat)}`} className="collection-card" key={c.cat}
                  data-reveal style={{ ["--i" as string]: i }}>
              <span className="collection-index">{String(i + 1).padStart(2, "0")}</span>
              {c.image && <img src={c.image} alt="" loading="lazy" />}
              <span className="collection-copy">
                <span className="collection-title">{c.title}</span>
                <span className="collection-line">{c.line}</span>
                <span className="collection-meta">{c.count} styles · from {formatPrice(c.from).replace(".00", "")}</span>
              </span>
              <span className="collection-arrow" aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ---------------- The Game ---------------- */}
      <section className="game" data-reveal>
        <div className="game-inner">
          <p className="section-num light">02 — Rivalry</p>
          <h2 className="display-xl">
            The <em>Game</em>.
          </h2>
          <p className="game-copy">
            Since 1875, one Saturday in November. Get stadium-ready with this season's rivalry tee,
            then layer up for the fourth quarter.
          </p>
          {rivalry && (
            <Link to={`/products/${rivalry.product_id}`} className="btn btn-brass">
              {displayName(rivalry.name)} · {formatPrice(rivalry.price).replace(".00", "")}
            </Link>
          )}
        </div>
        <div className="game-score" aria-hidden="true">
          <span>YALE</span><span className="vs">vs.</span><span>HARVARD</span>
        </div>
      </section>

      {/* ---------------- Editor's picks ---------------- */}
      {picks.length > 0 && (
        <section className="section">
          <header className="section-head" data-reveal>
            <p className="section-num">03 — Editor's Picks</p>
            <h2 className="display-sm">Pieces we <em>keep reaching for</em></h2>
          </header>
          <div className="product-grid">
            {picks.map((p, i) => <ProductTile p={p} index={i} key={p.product_id} />)}
          </div>
        </section>
      )}

      {/* ---------------- Concierge ---------------- */}
      <section className="section concierge-band" data-reveal>
        <div className="concierge-copy">
          <p className="section-num">04 — The Concierge</p>
          <h2 className="display-sm">A shop assistant that <em>actually checks the rack.</em></h2>
          <p>
            Ask for "a gray hoodie in medium" or "is this in pink?" Our concierge looks up live stock
            by size, fills this page with matches, and remembers you when you log in.
          </p>
          <button type="button" className="btn" onClick={() => openConcierge("What hoodies do you have?")}>
            Start a conversation
          </button>
        </div>
        <div className="concierge-demo" aria-hidden="true">
          <div className="demo-bubble user">Do you have this in pink?</div>
          <div className="demo-bubble bot">
            This one comes in <strong>navy blue and white</strong>, not pink. Want me to find something in a softer shade?
          </div>
          <div className="demo-chips"><span>Show me gray ones</span><span>What sizes are in stock?</span></div>
        </div>
      </section>
    </>
  );
}
