import axios from "axios";

// WHY a single configured axios instance instead of calling axios.get/post
// directly everywhere: token attachment and base URL are cross-cutting
// concerns. Centralizing them here means every request automatically
// carries auth, and switching from localhost to a deployed backend URL
// is a one-line env var change instead of a find-and-replace across
// every component.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;