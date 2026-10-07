import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.tsx";
import { Crest } from "../ui.tsx";

const EMPTY = { first_name: "", last_name: "", email: "", password: "", confirm_password: "" };

// Mirrors the server rules in backend/auth.py (the server is the source of truth).
function validate(f: typeof EMPTY): string | null {
  if (!f.first_name.trim() || !f.last_name.trim()) return "First and last name are required.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim())) return "Please enter a valid email address.";
  if (f.password.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Za-z]/.test(f.password) || !/\d/.test(f.password))
    return "Password must include at least one letter and one number.";
  if (f.password !== f.confirm_password) return "Passwords do not match.";
  return null;
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const update = (field: keyof typeof EMPTY) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value });

  const mismatch = form.confirm_password.length > 0 && form.password !== form.confirm_password;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const problem = validate(form);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await register(form);
      navigate("/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="section auth-layout">
      <aside className="auth-aside" data-reveal>
        <Crest size={56} className="crest-ivory" />
        <h2 className="display-sm">Join the <em>house.</em></h2>
        <p>A Campus Customs account takes a minute and makes shopping more personal.</p>
        <ul>
          <li>The Concierge remembers your conversations</li>
          <li>Pick up on any device after logging in</li>
          <li>Your password is hashed with PBKDF2</li>
        </ul>
      </aside>
      <div className="auth">
      <p className="section-num">New here</p>
      <h1 className="display-sm">Create Account</h1>
      <form className="form" onSubmit={handleSubmit} noValidate>
        <div className="row">
          <label>
            First name
            <input autoComplete="given-name" value={form.first_name} onChange={update("first_name")} required />
          </label>
          <label>
            Last name
            <input autoComplete="family-name" value={form.last_name} onChange={update("last_name")} required />
          </label>
        </div>
        <label>
          Email
          <input type="email" autoComplete="email" value={form.email} onChange={update("email")} required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={update("password")}
            required
          />
          <span className="hint">At least 8 characters, with a letter and a number.</span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={update("confirm_password")}
            aria-invalid={mismatch}
            required
          />
          {mismatch && <span className="hint hint-error">Passwords do not match.</span>}
        </label>
        {error && <p className="notice error-notice" role="alert">{error}</p>}
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Create Account"}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
      </div>
    </section>
  );
}
