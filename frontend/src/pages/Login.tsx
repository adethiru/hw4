import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.tsx";
import { Crest } from "../ui.tsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="section auth-layout">
      <aside className="auth-aside" data-reveal>
        <Crest size={56} className="crest-ivory" />
        <h2 className="display-sm">Welcome <em>back.</em></h2>
        <p>Log in to pick up your conversation with the Concierge where you left off.</p>
        <ul>
          <li>Your chat history, saved</li>
          <li>The Concierge greets you by name</li>
          <li>Passwords hashed: never stored in plain text</li>
        </ul>
      </aside>
      <div className="auth">
      <p className="section-num">Members</p>
      <h1 className="display-sm">Log In</h1>
      <form className="form" onSubmit={handleSubmit} noValidate>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="notice error-notice" role="alert">{error}</p>}
        <button className="btn" type="submit" disabled={submitting || !email || !password}>
          {submitting ? "Logging in…" : "Log In"}
        </button>
      </form>
      <p className="muted">
        New here? <Link to="/register">Create an account</Link>
      </p>
      </div>
    </section>
  );
}
