import { useState } from "react";
import api from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignup, setIsSignup] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = isSignup ? "/auth/signup" : "/auth/login";
      const res = await api.post(endpoint, { email, password });
      localStorage.setItem("token", res.data.access_token);
      onLogin();
    } catch (err) {
      setError(err.response?.data?.error || "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.brandRow}>
          <div style={styles.logoDot} />
          <span style={styles.brandName}>Job Scheduler</span>
        </div>

        <h1 style={styles.title}>{isSignup ? "Create your account" : "Welcome back"}</h1>
        <p style={styles.subtitle}>
          {isSignup ? "Set up an account to start scheduling jobs." : "Log in to manage your queues and jobs."}
        </p>

        <form onSubmit={submit} style={{ marginTop: 24 }}>
          <label style={styles.label}>Email</label>
          <input
            type="email"
            placeholder="name@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
            required
          />

          <label style={styles.label}>Password</label>
          <input
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
            required
          />

          {error && <div style={styles.errorBox}>{error}</div>}

          <button type="submit" disabled={loading} style={styles.primaryButton}>
            {loading ? "Please wait…" : isSignup ? "Sign up" : "Log in"}
          </button>
        </form>

        <p style={styles.switchRow}>
          {isSignup ? "Already have an account?" : "Need an account?"}{" "}
          <button onClick={() => setIsSignup(!isSignup)} style={styles.linkButton}>
            {isSignup ? "Log in" : "Sign up"}
          </button>
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(180deg, #f6f5f2 0%, #eeece5 100%)",
    fontFamily: "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  },
  card: {
    width: 380,
    background: "#ffffff",
    borderRadius: 14,
    border: "1px solid #e5e3dd",
    padding: "36px 32px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)",
  },
  brandRow: { display: "flex", alignItems: "center", gap: 8, marginBottom: 28 },
  logoDot: { width: 10, height: 10, borderRadius: "50%", background: "#378ADD" },
  brandName: { fontSize: 13, fontWeight: 600, letterSpacing: 0.3, color: "#6b6960", textTransform: "uppercase" },
  title: { fontSize: 22, fontWeight: 600, margin: 0, color: "#1f1e1c" },
  subtitle: { fontSize: 14, color: "#6b6960", margin: "6px 0 0" },
  label: { display: "block", fontSize: 13, fontWeight: 500, color: "#1f1e1c", marginBottom: 6, marginTop: 16 },
  input: {
    width: "100%",
    padding: "10px 12px",
    fontSize: 14,
    border: "1px solid #e5e3dd",
    borderRadius: 8,
    outline: "none",
    background: "#faf9f7",
  },
  errorBox: {
    marginTop: 14,
    padding: "10px 12px",
    background: "#FAECE7",
    color: "#712B13",
    borderRadius: 8,
    fontSize: 13,
  },
  primaryButton: {
    width: "100%",
    marginTop: 22,
    padding: "11px 0",
    background: "#1f1e1c",
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
  },
  switchRow: { textAlign: "center", fontSize: 13, color: "#6b6960", marginTop: 22 },
  linkButton: {
    background: "none",
    border: "none",
    color: "#185fa5",
    fontWeight: 600,
    fontSize: 13,
    padding: 0,
  },
};
