import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("access_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

let refreshing: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refresh_token = localStorage.getItem("refresh_token");
  if (!refresh_token) throw new Error("No refresh token");
  const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token });
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data.access_token;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        refreshing = refreshing || refreshAccessToken();
        const token = await refreshing;
        refreshing = null;
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
