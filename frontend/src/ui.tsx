/**
 * Shared presentation pieces for the Campus Customs storefront (Problem 10).
 * Design language: "Elm City Editorial" — an ivory, letterpress-style collegiate catalogue
 * with Yale-blue ink, brass foil accents, hairline rules and hang-tag product cards.
 */
import { Link } from "react-router-dom";
import { formatPrice } from "./api.ts";

export const SIZES = ["XS", "S", "M", "L", "XL", "XXL"];

/** Our own crest (not a Yale mark): a shield with an interlocked CC monogram and an elm leaf. */
export function Crest({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <svg className={`crest ${className}`} width={size} height={size * 1.15} viewBox="0 0 100 115" aria-hidden="true">
      <path d="M50 3 L94 14 V52 C94 82 74 101 50 112 C26 101 6 82 6 52 V14 Z" fill="currentColor" />
      <path d="M50 10 L87 19 V52 C87 77 70 93 50 103 C30 93 13 77 13 52 V19 Z" fill="none"
            stroke="var(--brass, #b08d57)" strokeWidth="2" />
      <text x="50" y="66" textAnchor="middle" fontFamily="Fraunces, Georgia, serif" fontSize="38"
            fontStyle="italic" fontWeight="600" fill="var(--ivory, #f6f1e7)" letterSpacing="-3">CC</text>
      <path d="M50 78 c-6 3 -9 9 -6 15 c5 -2 8 -8 6 -15 z M50 78 c6 3 9 9 6 15 c-5 -2 -8 -8 -6 -15 z"
            fill="var(--brass, #b08d57)" />
    </svg>
  );
}

/** Tidy catalogue names for display: "Berkeley 1 4 Zip" → "Berkeley ¼-Zip", "T Shirt" → "T-Shirt". */
export function displayName(name: string): string {
  return name
    .replace(/\b1 4 Zip\b/gi, "¼-Zip")
    .replace(/\bT Shirt\b/gi, "T-Shirt")
    .replace(/\bVs\b/g, "vs.")
    .replace(/\bUa\b/g, "UA")
    .replace(/\bVit\b/g, "VIT")
    .replace(/\s+\d+$/, "")
    .trim();
}

const SWATCHES: [RegExp, string][] = [
  [/navy/, "#14284b"], [/heather/, "#a9a9a6"], [/charcoal/, "#3b3d42"], [/gr[ae]y/, "#8e9196"],
  [/black/, "#16171a"], [/white|ivory|cream/, "#f7f5ef"], [/red|crimson|maroon/, "#9b2335"],
  [/coral|pink/, "#e38b78"], [/green/, "#2f6b4f"], [/yellow|gold/, "#d8b24a"], [/orange/, "#d9772b"],
  [/royal|blue/, "#2d5fa8"], [/brown|tan|khaki/, "#9a7b55"], [/purple/, "#5b3f7a"],
];
export const swatch = (color: string) => SWATCHES.find(([re]) => re.test(color.toLowerCase()))?.[1] ?? "#c9c2b3";

/** XS–XXL as small letters; sold-out sizes are struck through. */
export function SizeDots({ inStock }: { inStock: string[] }) {
  return (
    <span className="size-dots" aria-label={inStock.length ? `In stock: ${inStock.join(", ")}` : "Sold out"}>
      {SIZES.map((s) => (
        <span key={s} className={inStock.includes(s) ? "on" : "off"}>{s}</span>
      ))}
    </span>
  );
}

export interface TileProduct {
  product_id: string;
  name: string;
  price: number;
  category: string;
  image_url: string;
  short_description: string;
  sizes_in_stock: string[];
}

/** The hang-tag product card used on Home, Products and chat-search results. */
export function ProductTile({ p, index }: { p: TileProduct; index: number }) {
  return (
    <Link to={`/products/${p.product_id}`} className="tile" data-reveal style={{ ["--i" as string]: index % 12 }}>
      <figure className="tile-media">
        <img src={p.image_url} alt={displayName(p.name)} loading="lazy" />
        <span className="tile-cta">View the piece →</span>
      </figure>
      <div className="tile-tag">
        <span className="tile-hole" aria-hidden="true" />
        <p className="tile-kicker">
          <span>{p.category}</span>
          <span>No. {String(index + 1).padStart(3, "0")}</span>
        </p>
        <h3 className="tile-name">{displayName(p.name)}</h3>
        <p className="tile-blurb">{p.short_description}</p>
        <div className="tile-foot">
          <SizeDots inStock={p.sizes_in_stock} />
          <span className="price-tag">{formatPrice(p.price).replace(".00", "")}</span>
        </div>
      </div>
    </Link>
  );
}

/** Open the floating concierge from anywhere (see ChatWidget OPEN_CHAT_EVENT). */
export const openConcierge = (text = "") =>
  window.dispatchEvent(new CustomEvent("cc:open-chat", { detail: { text } }));
