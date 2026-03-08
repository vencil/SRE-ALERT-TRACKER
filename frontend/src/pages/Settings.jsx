import { useState, useEffect } from "react";
import {
  fetchClusters,
  triggerHealthCheck,
  triggerPoll,
  fetchPollerStatus,
  fetchFilters,
  createFilter,
  deleteFilter,
  fetchTasks,
  createTask,
  updateTask,
  fetchLabels,
  deleteLabel,
  mergeLabels,
  fetchMaintenanceWindows,
  createMaintenanceWindow,
  deleteMaintenanceWindow,
  fetchRetention,
  updateRetention,
  triggerPurge,
} from "../api/client";

/**
 * Settings 頁 — cluster status, poller control, filter rules management.
 */
export default function Settings() {
  return (
    <div className="space-y-8">
      <h1 className="text-xl font-bold text-gray-900">設定</h1>
      <ClusterSection />
      <PollerSection />
      <FilterSection />
      <TaskSection />
      <LabelSection />
      <MaintenanceSection />
      <RetentionSection />
    </div>
  );
}

/* ── Cluster 狀態 ───────────────────────────────────────── */
function ClusterSection() {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    fetchClusters()
      .then((data) => setClusters(Array.isArray(data?.clusters) ? data.clusters : Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleHealthCheck() {
    setChecking(true);
    try {
      const result = await triggerHealthCheck();
      setClusters(Array.isArray(result?.results) ? result.results : Array.isArray(result) ? result : []);
    } catch {
      /* ignore */
    } finally {
      setChecking(false);
    }
  }

  const statusColors = {
    healthy: "bg-green-500",
    unhealthy: "bg-red-500",
    unknown: "bg-gray-400",
    removed: "bg-gray-300",
  };

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">Clusters</h2>
        <button
          onClick={handleHealthCheck}
          disabled={checking}
          className="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 transition-colors"
        >
          {checking ? "檢查中..." : "Health Check"}
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">載入中...</p>
      ) : clusters.length === 0 ? (
        <p className="text-sm text-gray-400">尚無 cluster 設定</p>
      ) : (
        <div className="grid gap-2">
          {clusters.map((c) => (
            <div
              key={c.id || c.name}
              className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded"
            >
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${statusColors[c.status] || statusColors.unknown}`} />
                <span className="text-sm font-medium">{c.name}</span>
              </div>
              <span className="text-xs text-gray-500">{c.status}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Poller 控制 ──────────────────────────────────────── */
function PollerSection() {
  const [status, setStatus] = useState(null);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    fetchPollerStatus().then(setStatus).catch(() => {});
  }, []);

  async function handleTrigger() {
    setTriggering(true);
    try {
      await triggerPoll();
      const s = await fetchPollerStatus();
      setStatus(s);
    } catch {
      /* ignore */
    } finally {
      setTriggering(false);
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">Alert Poller</h2>
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {triggering ? "拉取中..." : "手動觸發拉取"}
        </button>
      </div>

      {status && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-500">Interval:</span>{" "}
            <span className="font-medium">{status.interval_hours}h</span>
          </div>
          <div>
            <span className="text-gray-500">Lookback:</span>{" "}
            <span className="font-medium">{status.lookback_hours}h</span>
          </div>
          <div>
            <span className="text-gray-500">Last run:</span>{" "}
            <span className="font-medium">{status.last_run_at || "never"}</span>
          </div>
          <div>
            <span className="text-gray-500">Status:</span>{" "}
            <span className="font-medium">{status.last_run_status}</span>
          </div>
        </div>
      )}
    </section>
  );
}

/* ── 每週例行任務 ─────────────────────────────────────── */
function TaskSection() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    fetchTasks()
      .then((data) => setTasks(Array.isArray(data?.tasks) ? data.tasks : Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    if (!title.trim()) return;
    setAdding(true);
    try {
      await createTask({ title: title.trim() });
      const data = await fetchTasks();
      setTasks(Array.isArray(data?.tasks) ? data.tasks : Array.isArray(data) ? data : []);
      setTitle("");
    } catch {
      /* ignore */
    } finally {
      setAdding(false);
    }
  }

  async function handleToggleActive(task) {
    try {
      await updateTask(task.id, { is_active: !task.is_active });
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, is_active: !task.is_active } : t)));
    } catch {
      /* ignore */
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="font-semibold text-gray-900 mb-4">每週例行任務</h2>

      <form onSubmit={handleAdd} className="flex gap-2 mb-4">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="新增任務名稱"
          maxLength={200}
          className="flex-1 text-sm px-3 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
        />
        <button
          type="submit"
          disabled={adding}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-900 disabled:opacity-50"
        >
          新增
        </button>
      </form>

      {loading ? (
        <p className="text-sm text-gray-500">載入中...</p>
      ) : tasks.length === 0 ? (
        <p className="text-sm text-gray-400">尚無任務</p>
      ) : (
        <div className="grid gap-1">
          {tasks.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded text-sm"
            >
              <span className={t.is_active ? "text-gray-700" : "text-gray-400 line-through"}>
                {t.title}
              </span>
              <button
                onClick={() => handleToggleActive(t)}
                className={`text-xs ${t.is_active ? "text-red-500 hover:text-red-700" : "text-green-600 hover:text-green-800"}`}
              >
                {t.is_active ? "停用" : "啟用"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── 標籤管理 ────────────────────────────────────────── */
function LabelSection() {
  const [labels, setLabels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mergeForm, setMergeForm] = useState({ source_id: "", target_id: "" });

  useEffect(() => {
    fetchLabels()
      .then((data) => setLabels(Array.isArray(data?.labels) ? data.labels : Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id) {
    try {
      await deleteLabel(id);
      setLabels((prev) => prev.filter((l) => l.id !== id));
    } catch {
      /* ignore */
    }
  }

  async function handleMerge(e) {
    e.preventDefault();
    const src = parseInt(mergeForm.source_id, 10);
    const tgt = parseInt(mergeForm.target_id, 10);
    if (Number.isNaN(src) || Number.isNaN(tgt) || src === tgt) return;
    try {
      await mergeLabels({ source_id: src, target_id: tgt });
      const data = await fetchLabels();
      setLabels(Array.isArray(data?.labels) ? data.labels : Array.isArray(data) ? data : []);
      setMergeForm({ source_id: "", target_id: "" });
    } catch {
      /* ignore */
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="font-semibold text-gray-900 mb-4">標籤管理</h2>

      {/* Merge form */}
      <form onSubmit={handleMerge} className="flex items-end gap-2 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">來源 Label</label>
          <select
            value={mergeForm.source_id}
            onChange={(e) => setMergeForm({ ...mergeForm, source_id: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            <option value="">選擇...</option>
            {labels.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>
        <span className="text-gray-400 pb-1.5">→</span>
        <div>
          <label className="block text-xs text-gray-500 mb-1">目標 Label</label>
          <select
            value={mergeForm.target_id}
            onChange={(e) => setMergeForm({ ...mergeForm, target_id: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            <option value="">選擇...</option>
            {labels.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="px-3 py-1.5 text-sm bg-amber-600 text-white rounded hover:bg-amber-700"
        >
          合併
        </button>
      </form>

      {loading ? (
        <p className="text-sm text-gray-500">載入中...</p>
      ) : labels.length === 0 ? (
        <p className="text-sm text-gray-400">尚無標籤</p>
      ) : (
        <div className="grid gap-1">
          {labels.map((l) => (
            <div
              key={l.id}
              className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded text-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: l.color || "#6b7280" }}
                />
                <span className="font-medium">{l.name}</span>
                {l.description && (
                  <span className="text-xs text-gray-400">{l.description}</span>
                )}
              </div>
              <button
                onClick={() => handleDelete(l.id)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                刪除
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── 維護窗口 ────────────────────────────────────────── */
function MaintenanceSection() {
  const [windows, setWindows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ cluster_id: "", start_time: "", end_time: "", reason: "" });
  const [adding, setAdding] = useState(false);
  const [clusters, setClusters] = useState([]);

  useEffect(() => {
    Promise.allSettled([
      fetchMaintenanceWindows().then((data) =>
        setWindows(Array.isArray(data?.windows) ? data.windows : Array.isArray(data) ? data : [])
      ),
      fetchClusters().then((data) =>
        setClusters(Array.isArray(data?.clusters) ? data.clusters : Array.isArray(data) ? data : [])
      ),
    ]).finally(() => setLoading(false));
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    if (!form.cluster_id || !form.start_time || !form.end_time) return;
    setAdding(true);
    try {
      await createMaintenanceWindow({
        cluster_id: parseInt(form.cluster_id, 10),
        start_time: form.start_time,
        end_time: form.end_time,
        reason: form.reason || null,
      });
      const data = await fetchMaintenanceWindows();
      setWindows(Array.isArray(data?.windows) ? data.windows : Array.isArray(data) ? data : []);
      setForm({ cluster_id: "", start_time: "", end_time: "", reason: "" });
    } catch {
      /* ignore */
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteMaintenanceWindow(id);
      setWindows((prev) => prev.filter((w) => w.id !== id));
    } catch {
      /* ignore */
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="font-semibold text-gray-900 mb-4">維護窗口</h2>

      <form onSubmit={handleAdd} className="flex items-end gap-2 mb-4 flex-wrap">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Cluster</label>
          <select
            value={form.cluster_id}
            onChange={(e) => setForm({ ...form, cluster_id: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            <option value="">選擇...</option>
            {clusters.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">開始時間</label>
          <input
            type="datetime-local"
            value={form.start_time}
            onChange={(e) => setForm({ ...form, start_time: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">結束時間</label>
          <input
            type="datetime-local"
            value={form.end_time}
            onChange={(e) => setForm({ ...form, end_time: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">原因</label>
          <input
            type="text"
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            placeholder="維護原因（選填）"
            className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
          />
        </div>
        <button
          type="submit"
          disabled={adding}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-900 disabled:opacity-50"
        >
          新增
        </button>
      </form>

      {loading ? (
        <p className="text-sm text-gray-500">載入中...</p>
      ) : windows.length === 0 ? (
        <p className="text-sm text-gray-400">尚無維護窗口</p>
      ) : (
        <div className="grid gap-1">
          {windows.map((w) => (
            <div
              key={w.id}
              className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded text-sm"
            >
              <div>
                <span className="font-medium">{w.cluster_name || `Cluster #${w.cluster_id}`}</span>
                <span className="text-gray-400 mx-2">|</span>
                <span className="text-gray-600">{w.start_time} ~ {w.end_time}</span>
                {w.reason && <span className="text-xs text-gray-400 ml-2">({w.reason})</span>}
              </div>
              <button
                onClick={() => handleDelete(w.id)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                刪除
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Filter 規則 ─────────────────────────────────────── */
function FilterSection() {
  const [filters, setFilters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ rule_type: "blacklist", filter_field: "alertname", filter_value: "" });
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    fetchFilters()
      .then((data) => setFilters(Array.isArray(data?.filters) ? data.filters : Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    if (!form.filter_value.trim()) return;
    setAdding(true);
    try {
      await createFilter(form);
      const data = await fetchFilters();
      setFilters(Array.isArray(data?.filters) ? data.filters : Array.isArray(data) ? data : []);
      setForm({ ...form, filter_value: "" });
    } catch {
      /* ignore */
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteFilter(id);
      setFilters((prev) => prev.filter((f) => f.id !== id));
    } catch {
      /* ignore */
    }
  }

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="font-semibold text-gray-900 mb-4">Filter Rules</h2>

      {/* Add form */}
      <form onSubmit={handleAdd} className="flex items-end gap-2 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Type</label>
          <select
            value={form.rule_type}
            onChange={(e) => setForm({ ...form, rule_type: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            <option value="blacklist">Blacklist</option>
            <option value="whitelist">Whitelist</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Field</label>
          <select
            value={form.filter_field}
            onChange={(e) => setForm({ ...form, filter_field: e.target.value })}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            <option value="alertname">alertname</option>
            <option value="group">group</option>
            <option value="severity">severity</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">Value (supports * wildcards)</label>
          <input
            type="text"
            value={form.filter_value}
            onChange={(e) => setForm({ ...form, filter_value: e.target.value })}
            placeholder="e.g. MariaDB*"
            className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
          />
        </div>
        <button
          type="submit"
          disabled={adding}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-900 disabled:opacity-50"
        >
          新增
        </button>
      </form>

      {/* Rules list */}
      {loading ? (
        <p className="text-sm text-gray-500">載入中...</p>
      ) : filters.length === 0 ? (
        <p className="text-sm text-gray-400">尚無過濾規則</p>
      ) : (
        <div className="grid gap-1">
          {filters.map((f) => (
            <div
              key={f.id}
              className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded text-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    f.rule_type === "whitelist"
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {f.rule_type}
                </span>
                <span className="text-gray-600">{f.filter_field}</span>
                <span className="font-medium">{f.filter_value}</span>
              </div>
              <button
                onClick={() => handleDelete(f.id)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                刪除
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Retention 管理 ──────────────────────────────────────── */
function RetentionSection() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState("");
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState(null);

  useEffect(() => {
    fetchRetention()
      .then((data) => {
        setConfig(data);
        setMonths(String(data?.retention_months ?? 12));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    const val = parseInt(months, 10);
    if (Number.isNaN(val) || val < 1 || val > 60) return;
    try {
      const updated = await updateRetention({ retention_months: val });
      setConfig(updated);
    } catch {
      /* ignore */
    }
  }

  async function handlePurge() {
    if (!window.confirm("確定要執行資料清理嗎？此操作不可復原。")) return;
    setPurging(true);
    setPurgeResult(null);
    try {
      const result = await triggerPurge();
      setPurgeResult(result);
    } catch {
      /* ignore */
    } finally {
      setPurging(false);
    }
  }

  if (loading) return null;

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <h2 className="font-semibold text-gray-900 mb-4">資料保留</h2>

      <div className="flex items-end gap-3 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">保留月數</label>
          <input
            type="number"
            min="1"
            max="60"
            value={months}
            onChange={(e) => setMonths(e.target.value)}
            className="w-24 text-sm px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
          />
        </div>
        <button
          onClick={handleSave}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-900"
        >
          儲存
        </button>
        <button
          onClick={handlePurge}
          disabled={purging}
          className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          {purging ? "清理中..." : "立即清理"}
        </button>
      </div>

      {config?.last_purge_at && (
        <p className="text-xs text-gray-400 mb-2">上次清理: {config.last_purge_at}</p>
      )}

      {purgeResult && (
        <div className="text-sm bg-green-50 border border-green-200 rounded p-3">
          清理完成 — 刪除 {purgeResult.reports_deleted} 份報表,{" "}
          {purgeResult.sections_deleted} 個區段,{" "}
          {purgeResult.alerts_deleted} 筆 alert
        </div>
      )}
    </section>
  );
}
