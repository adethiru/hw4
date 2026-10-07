import { Link } from "react-router-dom";
import { Crest, openConcierge } from "../ui.tsx";

const VALUES = [
  { n: "I", title: "Made for here", text: "College crests, school marks and varsity designs for New Haven, not generic merch with a logo added." },
  { n: "II", title: "Honest stock", text: "Every size is tracked on its own. If your size is gone, we say so, and point you to something that fits." },
  { n: "III", title: "For the whole family", text: "First-years, seniors before Commencement, alumni at reunion, parents in the stands: there's a piece for each." },
];

export default function About() {
  return (
    <article className="about">
      <header className="about-head" data-reveal>
        <p className="section-num">About Campus Customs</p>
        <h1 className="display">
          A small shop with <em>a long view of Broadway.</em>
        </h1>
      </header>

      <div className="about-body">
        <div className="about-text" data-reveal>
          <p className="dropcap">
            Campus Customs is a local apparel shop at 57 Broadway, a short walk from Yale's campus.
            We print and stock officially licensed Yale gear: the block-letter classics, vintage
            bulldog graphics, sport designs, and pieces for every residential college and graduate school.
          </p>
          <p>
            We think a good sweatshirt should feel like it belongs to Yale, worn on the walk to
            section, at the library at midnight, and in the stands in November. So we keep the rack
            focused: heavyweight fleece, clean tees, sharp quarter-zips and outerwear that can
            handle a New Haven winter.
          </p>
          <blockquote className="pullquote">
            “If you love Yale, there's something here for you.”
          </blockquote>
          <p>
            Shopping online? Our concierge (bottom right) can check sizes, colors and live stock for
            you, and if you have an account it'll remember your conversation next time.
          </p>
        </div>

        <aside className="visit-card" data-reveal>
          <Crest size={52} />
          <h2>Visit the shop</h2>
          <p className="visit-address">57 Broadway<br />New Haven, CT 06511</p>
          <hr />
          <p className="muted">Try things on, feel the fleece, and find your size in person.</p>
          <div className="visit-actions">
            <Link to="/products" className="btn">Browse online</Link>
            <button type="button" className="btn btn-ghost" onClick={() => openConcierge()}>Ask a question</button>
          </div>
        </aside>
      </div>

      <section className="values">
        {VALUES.map((v, i) => (
          <div className="value" key={v.n} data-reveal style={{ ["--i" as string]: i }}>
            <span className="value-n">{v.n}</span>
            <h3>{v.title}</h3>
            <p>{v.text}</p>
          </div>
        ))}
      </section>
    </article>
  );
}
