import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface LoginInput {
  email: string;
  password: string;
  totp_code?: string;
}

// Mirrors backend LoginResponse: either a normal token pair, or a
// "you must finish setting up 2FA first" challenge (no tokens issued yet).
export interface LoginResult {
  requires_2fa_setup: boolean;
  setup_token?: string;
  secret?: string;
  otpauth_url?: string;
  access_token?: string;
  refresh_token?: string;
}

function saveTokensAndGoHome(data: { access_token?: string; refresh_token?: string }, navigate: (path: string) => void) {
  if (data.access_token) localStorage.setItem("access_token", data.access_token);
  if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
  navigate("/");
}

export function useLogin() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (input: LoginInput): Promise<LoginResult> => {
      const { data } = await api.post("/auth/login", input);
      return data;
    },
    onSuccess: (data) => {
      // Mandatory 2FA: a fresh account (or one that hasn't finished
      // enrollment) gets a setup challenge instead of tokens — the caller
      // (Login page) is responsible for showing the QR/secret + code input
      // and does NOT navigate away until setup-confirm succeeds.
      if (data.requires_2fa_setup) return;
      saveTokensAndGoHome(data, navigate);
    },
  });
}

interface Confirm2FASetupInput {
  setup_token: string;
  totp_code: string;
}

// Completes mandatory 2FA enrollment right after a login that came back
// with requires_2fa_setup=true. Only after this succeeds is the user
// actually logged in.
export function useConfirm2FASetup() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (input: Confirm2FASetupInput) => {
      const { data } = await api.post("/auth/2fa/setup-confirm", input);
      return data as { access_token: string; refresh_token: string };
    },
    onSuccess: (data) => saveTokensAndGoHome(data, navigate),
  });
}

export function useRegister() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (input: { email: string; password: string }) => {
      const { data } = await api.post("/auth/register", input);
      return data;
    },
    onSuccess: () => navigate("/login"),
  });
}

export function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.location.href = "/login";
}

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem("access_token"));
}
