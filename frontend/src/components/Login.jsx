import { useState } from "react";
import api from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignup, setIsSignup] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const endpoint = isSignup ? "/auth/signup" : "/auth/login";
      const res = await api.post(endpoint, { email, password });
      localStorage.setItem("token", res.data.access_token);
      onLogin();
    } catch (err) {
      setError(err.response?.data?.error || "something went wrong");
    }
  };

  return (
    <div style={{ maxWidth: 360, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h2>{isSignup ? "Sign up" : "Log in"}</h2>
      <form onSubmit={submit}>
        <input
          type="email" placeholder="email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ display: "block", width: "100%", marginBottom: 8, padding: 8 }}
        />
        <input
          type="password" placeholder="password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ display: "block", width: "100%", marginBottom: 8, padding: 8 }}
        />
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" style={{ padding: "8px 16px" }}>
          {isSignup ? "Sign up" : "Log in"}
        </button>
      </form>
      <p style={{ marginTop: 12 }}>
        <button onClick={() => setIsSignup(!isSignup)} style={{ background: "none", border: "none", color: "blue", cursor: "pointer" }}>
          {isSignup ? "Already have an account? Log in" : "Need an account? Sign up"}
        </button>
      </p>
    </div>
  );
}