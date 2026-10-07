import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.tsx";
import { Crest } from "../ui.tsx";

const mainLinks = [
  { to: "/", label: "Home", end: true },
  { to: "/products", label: "Products" },
  { to: "/about", label: "About Us" },
];

const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");

export default function NavBar() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  // The bar is transparent ivory at the top and turns into frosted glass once you scroll.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className={`navbar${scrolled ? " scrolled" : ""}`}>
      <div className="navbar-inner">
        <NavLink to="/" className="brand" aria-label="Campus Customs home">
          <Crest size={30} />
          <span className="brand-text">
            <span className="brand-name">Campus Customs</span>
            <span className="brand-sub">New Haven · Est. on Broadway</span>
          </span>
        </NavLink>

        <nav className="nav-links" aria-label="Main">
          {mainLinks.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={linkClass}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="nav-auth">
          {loading ? null : user ? (
            <>
              <span className="nav-user">
                <span className="nav-avatar" aria-hidden="true">{(user.first_name ?? user.name).charAt(0)}</span>
                Hi, {user.first_name ?? user.name}
              </span>
              <button type="button" className="btn btn-ghost btn-small" onClick={handleLogout}>
                Log Out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={linkClass}>
                Log In
              </NavLink>
              <NavLink to="/register" className="btn btn-small">
                Create Account
              </NavLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
