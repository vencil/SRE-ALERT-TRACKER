import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchReports, createReport } from "../api/client";

/**
 * Get ISO year and week number for a given date.
 * Uses the standard ISO 8601 week date algorithm.
 */
function getISOYearWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return { year: d.getUTCFullYear(), week: weekNo };
}

/**
 * 週報列表頁 — shows all shift reports by year/week.
 * Displays alert count and fill-rate per report.
 */
export default function ReportList() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadReports();
  }, []);

  async function loadReports() {
    setLoading(true);
    try {
      const data = await fetchReports({ limit: 50, offset: 0 });
      setReports(data.reports || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateThisWeek() {
    setCreating(true);
    try {
      const now = new Date();
      const { year, week } = getISOYearWeek(now);
      await createReport({ year, week_number: week });
      await loadReports();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-500">載入中...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">週報列表</h1>
        <button
          onClick={handleCreateThisWeek}
          disabled={creating}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "建立中..." : "建立本週報表"}
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {reports.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          尚無報表。點擊上方按鈕建立本週報表。
        </div>
      ) : (
        <div className="grid gap-3">
          {reports.map((r) => (
            <Link
              key={r.id}
              to={`/reports/${r.id}`}
              className="block bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-lg font-semibold text-gray-900">
                    {r.year} 年第 {r.week_number} 週
                  </span>
                  {r.operator_name && (
                    <span className="ml-3 text-sm text-gray-500">值班: {r.operator_name}</span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>{r.alert_count ?? 0} alerts</span>
                  <span className="text-xs text-gray-400">
                    {r.daily_sections?.length || 0} days
                  </span>
                </div>
              </div>
              {r.daily_sections && r.daily_sections.length > 0 && (
                <div className="mt-2 flex gap-1">
                  {r.daily_sections.map((s) => (
                    <span
                      key={s.id}
                      className="w-8 h-1.5 rounded-full bg-gray-200"
                      title={s.section_date}
                    />
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
