import { useState } from "react";
import { Link } from "react-router-dom";
import { useLogin } from "../hooks/useAuth";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const login = useLogin();

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        className="w-full max-w-sm bg-panel border border-line rounded-xl p-8"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate({ email, password, totp_code: totp || undefined });
        }}
      >
        <h1 className="text-xl font-semibold mb-1">RemoteHub</h1>
        <p className="text-muted text-sm mb-6">Sign in to manage your machines.</p>

        <label className="block text-sm text-muted mb-1">Email</label>
        <input
          className="w-full mb-4 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <label className="block text-sm text-muted mb-1">Password</label>
        <input
          className="w-full mb-4 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <label className="block text-sm text-muted mb-1">2FA code (if enabled)</label>
        <input
          className="w-full mb-6 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent mono"
          placeholder="123456"
          value={totp}
          onChange={(e) => setTotp(e.target.value)}
        />

        {login.isError && (
          <p className="text-danger text-sm mb-4">Incorrect email, password, or 2FA code.</p>
        )}

        <button
          className="w-full bg-accent hover:opacity-90 transition rounded-lg py-2 font-medium"
          type="submit"
          disabled={login.isPending}
        >
          {login.isPending ? "Signing in..." : "Sign in"}
        </button>

        <p className="text-muted text-sm mt-6 text-center">
          No account? <Link to="/register" className="text-accent">Create one</Link>
        </p>
      </form>
    </div>
  );
}
