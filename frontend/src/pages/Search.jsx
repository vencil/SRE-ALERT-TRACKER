import { useState, useEffect } from "react";
import { fetchAlerts, fetchClusters, fetchLabels } from "../api/client";
import AlertCard from "../components/AlertCard";

/**
 * 歷史查詢頁 — search alerts with filters: label, cluster, severity, year/week.
 */
export default function Search() {
  const [alerts, setAlerts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [labels, setLabels] = useState([]);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [filters, setFilters] = useState({
    cluster_id: "",
    severity: "",
    label_id: "",
    year: "",
    week: "",
  });

  useEffect(() => {
    fetchClusters()
      .then((d) => setClusters(Array.isArray(d?.clusters) ? d.clusters : []))
      .catch(() => setClusters([]));
    fetchLabels()
      .then((d) => setLabels(Array.isArray(d?.labels) ? d.labels : []))
      .catch(() => setLabels([]));
  }, []);

  async function handleSearch(newOffset = 0) {
    setLoading(true);
    setOffset(newOffset);
    setError(null);
    try {
      const params = { offset: newOffset, limit };
      if (filters.cluster_id) params.cluster_id = filters.cluster_id;
      if (filters.severity) params.severity = filters.severity;
      if (filters.label_id) params.label_id = filters.label_id;
      if (filters.year) params.year = filters.year;
      if (filters.week) params.week = filters.week;

      const data = await fetchAlerts(params);
      setAlerts(data.alerts ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err.message || "搜尋失敗");
      setAlerts([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  function handleFilterChange(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900 mb-4">歷史查詢</h1>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Cluster</label>
            <select
              value={filters.cluster_id}
              onChange={(e) => handleFilterChange("cluster_id", e.target.value)}
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded"
            >
              <option value="">全部</option>
              {clusters.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Severity</label>
            <select
              value={filters.severity}
              onChange={(e) => handleFilterChange("severity", e.target.value)}
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded"
            >
              <option value="">全部</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Label</label>
            <select
              value={filters.label_id}
              onChange={(e) => handleFilterChange("label_id", e.target.value)}
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded"
            >
              <option value="">全部</option>
              {labels.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Year</label>
            <input
              type="number"
              min="2020"
              max="2099"
              value={filters.year}
              onChange={(e) => handleFilterChange("year", e.target.value)}
              placeholder="e.g. 2026"
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Week</label>
            <input
              type="number"
              min="1"
              max="53"
              value={filters.week}
              onChange={(e) => handleFilterChange("week", e.target.value)}
              placeholder="1-53"
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded"
            />
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={() => handleSearch(0)}
            disabled={loading}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "搜尋中..." : "搜尋"}
          </button>
          <span className="text-sm text-gray-500">
            {total > 0 ? `共 ${total} 筆結果` : ""}
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {/* Results */}
      {alerts.length > 0 ? (
        <div className="space-y-3">
          {alerts.map((a) => (
            <AlertCard key={a.id} alert={a} />
          ))}
        </div>
      ) : (
        !loading && (
          <div className="text-center py-12 text-gray-400">
            輸入篩選條件後點擊搜尋
          </div>
        )
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            onClick={() => handleSearch(offset - limit)}
            disabled={offset === 0}
            className="px-3 py-1 text-sm border rounded disabled:opacity-30"
          >
            上一頁
          </button>
          <span className="text-sm text-gray-500">
            第 {currentPage} / {totalPages} 頁
          </span>
          <button
            onClick={() => handleSearch(offset + limit)}
            disabled={offset + limit >= total}
            className="px-3 py-1 text-sm border rounded disabled:opacity-30"
          >
            下一頁
          </button>
        </div>
      )}
    </div>
  );
}
