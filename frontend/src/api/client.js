/**
 * Centralized API client using axios.
 * All requests go to the FastAPI backend.
 */
import axios from "axios";

let rawApiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
if (rawApiUrl) {
  rawApiUrl = rawApiUrl.trim();
  // Auto-prepend https:// if the protocol is missing from an absolute domain
  if (!/^https?:\/\//i.test(rawApiUrl) && !rawApiUrl.startsWith("/")) {
    rawApiUrl = `https://${rawApiUrl}`;
  }
  // Ensure it ends with /api/v1
  if (!rawApiUrl.endsWith("/api/v1") && !rawApiUrl.endsWith("/api/v1/")) {
    rawApiUrl = rawApiUrl.endsWith("/") ? `${rawApiUrl}api/v1` : `${rawApiUrl}/api/v1`;
  }
}
const BASE_URL = rawApiUrl;

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 2 min for AI inference
});

// ── Request interceptor (add auth headers here if needed) ──────────────────
api.interceptors.request.use((config) => {
  return config;
});

// ── Response interceptor ───────────────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail || error.message || "Unknown error";
    console.error("[API Error]", message);
    return Promise.reject(new Error(message));
  }
);

// ── Typed API methods ──────────────────────────────────────────────────────

export const uploadApi = {
  processImage: (formData) =>
    api.post("/upload/image", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  processBatch: (formData) =>
    api.post("/upload/batch", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};

export const violationsApi = {
  list: (params) => api.get("/violations", { params }),
  get: (id) => api.get(`/violations/${id}`),
  update: (id, data) => api.put(`/violations/${id}`, data),
  delete: (id) => api.delete(`/violations/${id}`),
  searchByPlate: (plate, params) =>
    api.get("/violations/search/plate", { params: { plate, ...params } }),
};

export const analyticsApi = {
  summary: () => api.get("/analytics/summary"),
  byType: () => api.get("/analytics/by-type"),
  trends: (params) => api.get("/analytics/trends", { params }),
  heatmap: () => api.get("/analytics/heatmap"),
  byCamera: () => api.get("/analytics/by-camera"),
};

export const reportsApi = {
  downloadCsv: (params) =>
    api.get("/reports/csv", {
      params,
      responseType: "blob",
    }),
  downloadPdf: (params) =>
    api.get("/reports/pdf", {
      params,
      responseType: "blob",
    }),
};

export const liveApi = {
  getWebSocketUrl: () => {
    const base = BASE_URL.replace(/^http/, "ws");
    return `${base}/live/ws`;
  },
  status: () => api.get("/live/status"),
  processVideo: (formData) =>
    api.post("/live/process-video", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 600000, // 10 min for video processing
    }),
};

export default api;
