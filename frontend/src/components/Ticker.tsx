const LINES = [
  "Officially licensed Yale apparel",
  "57 Broadway · New Haven, Connecticut",
  "Sizes XS to XXL",
  "Ask the Concierge about any piece",
  "Boola Boola",
];

/** Thin announcement marquee above the nav. Text is duplicated so the loop is seamless. */
export default function Ticker() {
  const row = LINES.map((l, i) => (
    <span key={i} className="ticker-item">
      {l}
      <span className="ticker-star" aria-hidden="true">✦</span>
    </span>
  ));
  return (
    <div className="ticker" role="note" aria-label={LINES.join(". ")}>
      <div className="ticker-track" aria-hidden="true">
        {row}
        {row}
      </div>
    </div>
  );
}
