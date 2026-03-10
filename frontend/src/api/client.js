/**
 * API client — Axios wrapper for backend communication.
 *
 * In dev mode, Vite proxy handles /api → localhost:8000.
 * In production, the same origin serves both static files and API.
 */
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 8000,
  headers: { "Content-Type": "application/json" },
});

// Response interceptor — unwrap data, normalize errors
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const message =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      "Unknown error";
    console.error(`[API] ${err.config?.method?.toUpperCase()} ${err.config?.url} — ${message}`);
    return Promise.reject({ message, status: err.response?.status });
  },
);

// ── Reports ──────────────────────────────────────────────
export const fetchReports = (params) => api.get("/reports", { params });
export const fetchReport = (id) => api.get(`/reports/${id}`);
export const createReport = (data) => api.post("/reports", data);
export const updateReport = (id, data) => api.patch(`/reports/${id}`, data);

// ── Sections ─────────────────────────────────────────────
export const updateSection = (id, data) => api.patch(`/sections/${id}`, data);

// ── Alerts ───────────────────────────────────────────────
export const fetchAlerts = (params) => api.get("/alerts", { params });
export const fetchAlert = (id) => api.get(`/alerts/${id}`);
export const updateAlert = (id, data) => api.patch(`/alerts/${id}`, data);
export const addAlertLabel = (alertId, labelId) =>
  api.post(`/alerts/${alertId}/labels`, { label_id: labelId });
export const removeAlertLabel = (alertId, labelId) =>
  api.delete(`/alerts/${alertId}/labels/${labelId}`);

// ── Labels ───────────────────────────────────────────────
export const fetchLabels = () => api.get("/labels");
export const createLabel = (data) => api.post("/labels", data);

// ── Clusters ─────────────────────────────────────────────
export const fetchClusters = (config) => api.get("/clusters", config);
export const triggerHealthCheck = () => api.post("/clusters/health-check");

// ── Poller ───────────────────────────────────────────────
export const fetchPollerStatus = () => api.get("/poller/status");
export const triggerPoll = () => api.post("/poller/trigger");

// ── Filters ──────────────────────────────────────────────
export const fetchFilters = () => api.get("/filters");
export const createFilter = (data) => api.post("/filters", data);
export const deleteFilter = (id) => api.delete(`/filters/${id}`);

// ── Dashboard ────────────────────────────────────────────
export const fetchTrends = (params, config) => api.get("/dashboard/trends", { params, ...config });
export const fetchTopAlerts = (params, config) => api.get("/dashboard/top-alerts", { params, ...config });
export const fetchSeverityDist = (params, config) => api.get("/dashboard/severity-distribution", { params, ...config });

// ── Export ───────────────────────────────────────────────
export const exportReportUrl = (id, format = "csv") =>
  `/api/export/report/${id}?format=${format}`;
export const exportAlertsUrl = (params) => {
  const qs = new URLSearchParams(params).toString();
  return `/api/export/alerts${qs ? "?" + qs : ""}`;
};

// ── Tasks ────────────────────────────────────────────────
export const fetchTasks = (params) => api.get("/tasks", { params });
export const createTask = (data) => api.post("/tasks", data);
export const updateTask = (id, data) => api.patch(`/tasks/${id}`, data);
export const fetchReportTasks = (reportId) => api.get(`/reports/${reportId}/tasks`);
export const toggleReportTask = (reportId, taskId, data) =>
  api.patch(`/reports/${reportId}/tasks/${taskId}`, data);

// ── Labels (advanced) ───────────────────────────────────
export const deleteLabel = (id) => api.delete(`/labels/${id}`);
export const mergeLabels = (data) => api.post("/labels/merge", data);

// ── Maintenance ─────────────────────────────────────────
export const fetchMaintenanceWindows = (params) => api.get("/maintenance", { params });
export const createMaintenanceWindow = (data) => api.post("/maintenance", data);
export const deleteMaintenanceWindow = (id) => api.delete(`/maintenance/${id}`);

// ── Auth / User ─────────────────────────────────────────
export const fetchCurrentUser = () => api.get("/me");

// ── Admin ───────────────────────────────────────────────
export const fetchRetention = () => api.get("/admin/retention");
export const updateRetention = (data) => api.patch("/admin/retention", data);
export const triggerPurge = (months) =>
  api.post("/admin/purge", null, { params: months ? { months } : {} });

export default api;
