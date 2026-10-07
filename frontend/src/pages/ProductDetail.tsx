import { useEffect, useState, type MouseEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { formatPrice, getProduct, type ProductDetail as Product } from "../api.ts";
import { useChatResults } from "../chatResults.tsx";
import { productsUrl } from "../navMemory.ts";
import { OPEN_CHAT_EVENT } from "../components/ChatWidget.tsx";
import { displayName, swatch } from "../ui.tsx";

function stockLabel(q: number) {
  if (q === 0) return "Sold out";
  if (q <= 3) return `Only ${q} left`;
  return `${q} in stock`;
}

export default function ProductDetail() {
  const { productId = "" } = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const { results } = useChatResults();

  // Same single-item page whether the shopper came from the full catalogue, chat-search
  // results on the Products page, or a card inside the chat bubble. Always open at the top.
  const backLabel = results ? `← Back to “${results.heading}” results` : "← Back to products";

  useEffect(() => {
    window.scrollTo(0, 0);
    setProduct(null);
    setError("");
    setSelected(null);
    getProduct(productId)
      .then(setProduct)
      .catch((e: Error) =>
        setError(e.message === "Not found" ? "We couldn't find that product." : "Couldn't load this product."),
      );
  }, [productId]);

  if (error) {
    return (
      <section className="section">
        <p className="placeholder error">{error}</p>
        <Link to={productsUrl()} className="back-link">{backLabel}</Link>
      </section>
    );
  }
  if (!product) {
    return (
      <section className="section">
        <div className="detail">
          <div className="detail-frame skeleton" />
          <div className="detail-info"><div className="skeleton-lines" /></div>
        </div>
      </section>
    );
  }

  const chosen = product.sizes.find((s) => s.size === selected);
  const status = (q: number) => (q === 0 ? "out" : q <= 3 ? "low" : "in");

  // Magnifier: the image zooms toward the cursor while hovering the frame.
  function onZoom(e: MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--zx", `${((e.clientX - r.left) / r.width) * 100}%`);
    e.currentTarget.style.setProperty("--zy", `${((e.clientY - r.top) / r.height) * 100}%`);
  }

  return (
    <section className="section">
      <Link to={productsUrl()} className="back-link">{backLabel}</Link>
      <div className="detail">
        <figure className="detail-frame">
          <div className="detail-zoom" onMouseMove={onZoom}>
            <img src={product.image_url} alt={displayName(product.name)} />
          </div>
          <figcaption>
            <span>Plate · {product.product_id}</span>
            <span>Campus Customs, New Haven</span>
          </figcaption>
        </figure>

        <div className="detail-info">
          <p className="section-num">{product.garment_type}</p>
          <h1 className="display-sm">{displayName(product.name)}</h1>
          <div className="detail-price-row">
            <span className="price-tag price-tag-lg">{formatPrice(product.price).replace(".00", "")}</span>
            <span className={`stock-pill ${product.total_stock > 0 ? "in" : "out"}`}>
              {product.total_stock > 0 ? "In stock at 57 Broadway" : "Currently sold out"}
            </span>
          </div>
          <p className="detail-desc">{product.description}</p>

          {product.colors.length > 0 && (
            <div className="detail-block">
              <h3 className="block-label">Colorway</h3>
              <div className="swatches">
                {product.colors.map((c) => (
                  <span className="swatch" key={c}>
                    <span className="swatch-dot" style={{ background: swatch(c) }} />
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="detail-block">
            <h3 className="block-label">
              Size <span className="block-hint">{chosen ? `${chosen.size}: ${stockLabel(chosen.quantity)}` : "Select a size"}</span>
            </h3>
            <div className="sizes">
              {product.sizes.map((s) => (
                <button
                  key={s.size}
                  type="button"
                  className={`size-btn${selected === s.size ? " selected" : ""}`}
                  disabled={!s.in_stock}
                  onClick={() => setSelected(s.size)}
                  title={stockLabel(s.quantity)}
                  aria-pressed={selected === s.size}
                >
                  {s.size}
                </button>
              ))}
            </div>
          </div>

          <div className="detail-block">
            <h3 className="block-label">Availability by size</h3>
            <table className="stock-table">
              <thead><tr><th>Size</th><th>Availability</th></tr></thead>
              <tbody>
                {product.sizes.map((s) => (
                  <tr key={s.size} className={`st-${status(s.quantity)}${selected === s.size ? " is-selected" : ""}`}>
                    <td>{s.size}</td>
                    <td><span className="st-dot" aria-hidden="true" />{stockLabel(s.quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            type="button"
            className="concierge-cta"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent(OPEN_CHAT_EVENT, {
                  detail: { text: selected ? `Do you have this in ${selected}?` : "" },
                }),
              )
            }
          >
            <span className="pulse-dot" aria-hidden="true" />
            <span>
              <strong>Ask the Concierge about this</strong>
              <small>Sizes, colors, similar pieces: answered from live stock</small>
            </span>
            <span aria-hidden="true">→</span>
          </button>

          {product.tags.length > 0 && (
            <p className="tags">{product.tags.map((t) => <span key={t}>#{t.replace(/\s+/g, "")}</span>)}</p>
          )}
        </div>
      </div>
    </section>
  );
}
