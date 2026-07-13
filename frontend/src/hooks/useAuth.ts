import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface LoginInput {
  email: string;
  password: string;
  totp_code?: string;
}

export function useLogin() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (input: LoginInput) => {
      const { data } = await api.post("/auth/login", input);
      return data;
    },
    onSuccess: (data) => {
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      navigate("/");
    },
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
