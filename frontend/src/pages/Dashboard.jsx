import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie,
} from "recharts";
import { fetchTrends, fetchTopAlerts, fetchSeverityDist, fetchClusters } from "../api/client";

const COLORS = ["#6366f1", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899"];
const SEVERITY_COLORS = { critical: "#ef4444", warning: "#f59e0b", info: "#3b82f6" };

export default function Dashboard() {
  const [trends, setTrends] = useState([]);
  const [topAlerts, setTopAlerts] = useState([]);
  const [severityDist, setSeverityDist] = useState([]);
  const [clusterMap, setClusterMap] = useState({});
  const [weeks, setWeeks] = useState(12);
  const [loading, setLoading] = useState(true);
  const [partialError, setPartialError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, [weeks]);

  async function loadData(signal) {
    setLoading(true);
    try {
      const opts = signal ? { signal } : {};
      const results = await Promise.allSettled([
        fetchTrends({ weeks }, opts),
        fetchTopAlerts({ weeks: Math.min(weeks, 4) }, opts),
        fetchSeverityDist({ weeks: Math.min(weeks, 4) }, opts),
        fetchClusters(opts),
      ]);

      if (signal?.aborted) return;

      const hasFailure = results.some((r) => r.status === "rejected");
      setPartialError(hasFailure);

      const trendData = results[0].status === "fulfilled" ? results[0].value : { trends: [] };
      const topData = results[1].status === "fulfilled" ? results[1].value : { top_alerts: [] };
      const sevData = results[2].status === "fulfilled" ? results[2].value : { distribution: [] };
      const clusterData = results[3].status === "fulfilled" ? results[3].value : { clusters: [] };

      // Build cluster ID → name map
      const clusters = Array.isArray(clusterData?.clusters) ? clusterData.clusters : [];
      const cMap = {};
      clusters.forEach((c) => (cMap[c.id] = c.name));
      setClusterMap(cMap);

      // Transform trends for Recharts: group by week, columns per cluster
      const weekMap = {};
      for (const t of trendData.trends ?? []) {
        const key = `${t.year}-W${String(t.week_number).padStart(2, "0")}`;
        if (!weekMap[key]) weekMap[key] = { week: key };
        const clusterName = cMap[t.cluster_id] || `Cluster ${t.cluster_id}`;
        weekMap[key][clusterName] = t.alert_count;
      }
      const sortedTrends = Object.values(weekMap).sort((a, b) => a.week.localeCompare(b.week));
      setTrends(sortedTrends);

      setTopAlerts(topData.top_alerts ?? []);
      setSeverityDist(sevData.distribution ?? []);
    } catch (err) {
      if (err?.name === "AbortError" || err?.message === "canceled") return;
      console.warn("Dashboard load failed:", err);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  // Get unique cluster names from trend data
  const clusterNames = trends.length > 0
    ? Object.keys(trends[0]).filter((k) => k !== "week")
    : [];

  if (loading) return <div className="text-center py-12 text-gray-500">載入中...</div>;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">趨勢儀表板</h1>
        <select
          value={weeks}
          onChange={(e) => setWeeks(Number(e.target.value))}
          className="text-sm px-2 py-1.5 border border-gray-200 rounded"
        >
          <option value={4}>最近 4 週</option>
          <option value={12}>最近 12 週</option>
          <option value={26}>最近 26 週</option>
          <option value={52}>最近 52 週</option>
        </select>
      </div>

      {partialError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-lg px-4 py-2">
          部分資料載入失敗，顯示內容可能不完整。
        </div>
      )}

      {/* Weekly trend line chart */}
      <section className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="font-semibold text-gray-900 mb-4">每週 Alert 趨勢</h2>
        {trends.length === 0 ? (
          <div className="text-sm text-gray-400 py-8 text-center">尚無趨勢資料</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              {clusterNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Top-N bar chart */}
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-gray-900 mb-4">最頻繁 Alert (Top 10)</h2>
          {topAlerts.length === 0 ? (
            <div className="text-sm text-gray-400 py-8 text-center">尚無資料</div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topAlerts} layout="vertical" margin={{ left: 100 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="alert_name"
                  tick={{ fontSize: 11 }}
                  width={90}
                />
                <Tooltip />
                <Bar dataKey="total_count" name="Count">
                  {topAlerts.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={SEVERITY_COLORS[entry.severity] || COLORS[i % COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Severity distribution pie */}
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Severity 分布</h2>
          {severityDist.length === 0 ? (
            <div className="text-sm text-gray-400 py-8 text-center">尚無資料</div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={severityDist}
                  dataKey="count"
                  nameKey="severity"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ severity, count }) => `${severity}: ${count}`}
                >
                  {severityDist.map((entry) => (
                    <Cell
                      key={entry.severity}
                      fill={SEVERITY_COLORS[entry.severity] || "#6b7280"}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>
    </div>
  );
}
