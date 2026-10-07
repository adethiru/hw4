import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="section notfound">
      <p className="section-num">Error 404</p>
      <h1 className="display">This page <em>wandered off campus.</em></h1>
      <p className="lead">Let's get you back to Broadway.</p>
      <Link to="/" className="btn">Back home</Link>
    </section>
  );
}
