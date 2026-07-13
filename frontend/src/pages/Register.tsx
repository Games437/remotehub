import { useState } from "react";
import { Link } from "react-router-dom";
import { useRegister } from "../hooks/useAuth";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const register = useRegister();

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form
        className="w-full max-w-sm bg-panel border border-line rounded-xl p-8"
        onSubmit={(e) => {
          e.preventDefault();
          register.mutate({ email, password });
        }}
      >
        <h1 className="text-xl font-semibold mb-1">Create your account</h1>
        <p className="text-muted text-sm mb-6">We'll email you a verification link.</p>

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
          className="w-full mb-2 bg-base border border-line rounded-lg px-3 py-2 outline-none focus:border-accent"
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <p className="text-muted text-xs mb-6">At least 8 characters.</p>

        {register.isError && (
          <p className="text-danger text-sm mb-4">Could not create account — email may already be registered.</p>
        )}

        <button
          className="w-full bg-accent hover:opacity-90 transition rounded-lg py-2 font-medium"
          type="submit"
          disabled={register.isPending}
        >
          {register.isPending ? "Creating..." : "Create account"}
        </button>

        <p className="text-muted text-sm mt-6 text-center">
          Already have an account? <Link to="/login" className="text-accent">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
