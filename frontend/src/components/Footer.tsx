import { Link } from "react-router-dom";
import { Crest } from "../ui.tsx";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <Crest size={44} className="crest-ivory" />
          <p className="footer-motto">
            Dressed for <em>the Elm City.</em>
          </p>
          <p className="footer-small">Officially licensed Yale apparel, printed and stocked in New Haven.</p>
        </div>
        <div className="footer-col">
          <h4>Visit</h4>
          <p>57 Broadway<br />New Haven, CT 06511</p>
        </div>
        <div className="footer-col">
          <h4>Shop</h4>
          <Link to="/products?cat=hoodie">Hoodies</Link>
          <Link to="/products?cat=crewneck">Crewnecks</Link>
          <Link to="/products?cat=t-shirt">Tees</Link>
          <Link to="/products?cat=jacket">Jackets</Link>
        </div>
        <div className="footer-col">
          <h4>House</h4>
          <Link to="/about">About Us</Link>
          <Link to="/login">Log In</Link>
          <Link to="/register">Create Account</Link>
        </div>
      </div>
      <div className="footer-word" aria-hidden="true">Boola.</div>
      <div className="footer-base">
        <span>© Campus Customs · New Haven</span>
        <span>Student project · AI Foundations, Homework 4</span>
      </div>
    </footer>
  );
}
