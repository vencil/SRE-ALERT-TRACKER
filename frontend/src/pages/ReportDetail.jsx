import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchReport, updateReport, updateSection, fetchAlerts, fetchReportTasks, toggleReportTask } from "../api/client";
import AlertCard from "../components/AlertCard";
import ExportButton from "../components/ExportButton";

/**
 * 週報明細頁 — shows daily sections with alert cards.
 * Supports editing operator name and per-section notes.
 */
export default function ReportDetail() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [alertsBySection, setAlertsBySection] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedSections, setExpandedSections] = useState(new Set());
  const [tasks, setTasks] = useState([]);
  const [alertsTruncated, setAlertsTruncated] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchReport(id);
      setReport(r);

      // Expand all sections by default
      const ids = new Set((r.daily_sections ?? []).map((s) => s.id));
      setExpandedSections(ids);

      // Load alerts filtered by this report's year/week (not all alerts)
      const ALERT_LIMIT = 500;
      const alerts = await fetchAlerts({
        year: r.year,
        week: r.week_number,
        limit: ALERT_LIMIT,
      });
      const alertList = alerts.alerts ?? [];
      setAlertsTruncated(alertList.length >= ALERT_LIMIT);
      const grouped = {};
      for (const a of alertList) {
        const sid = a.daily_section_id;
        if (!grouped[sid]) grouped[sid] = [];
        grouped[sid].push(a);
      }
      setAlertsBySection(grouped);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (id) {
      fetchReportTasks(id)
        .then((data) => setTasks(Array.isArray(data?.tasks) ? data.tasks : []))
        .catch(() => {});
    }
  }, [id]);

  function toggleSection(sectionId) {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  }

  async function handleOperatorChange(value) {
    try {
      const updated = await updateReport(id, { operator_name: value });
      setReport(updated);
    } catch (err) {
      console.warn("Failed to update operator name:", err);
    }
  }

  async function handleSectionNote(sectionId, note) {
    try {
      await updateSection(sectionId, { operator_name: note });
    } catch (err) {
      console.warn("Failed to update section note:", err);
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">載入中...</div>;
  if (error) return <div className="text-center py-12 text-red-600">{error}</div>;
  if (!report) return <div className="text-center py-12 text-gray-400">找不到報表</div>;

  async function handleToggleTask(taskId, currentChecked) {
    try {
      await toggleReportTask(id, taskId, { is_checked: !currentChecked });
      setTasks((prev) =>
        prev.map((t) => (t.task_id === taskId ? { ...t, is_checked: !currentChecked } : t))
      );
    } catch {
      /* toggle is non-critical */
    }
  }

  const weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-sm text-indigo-600 hover:underline">
            &larr; 返回列表
          </Link>
          <h1 className="text-xl font-bold text-gray-900 mt-1">
            {report.year} 年第 {report.week_number} 週
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <ExportButton reportId={id} />
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">值班人員:</label>
            <input
              type="text"
              defaultValue={report.operator_name || ""}
              onBlur={(e) => handleOperatorChange(e.target.value)}
              placeholder="填寫值班人員"
              className="text-sm px-3 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
            />
          </div>
        </div>
      </div>

      {/* Weekly Tasks */}
      {tasks.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">每週例行任務</h2>
          <div className="space-y-2">
            {tasks.map((t) => (
              <label
                key={t.task_id}
                className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 px-2 py-1 rounded"
              >
                <input
                  type="checkbox"
                  checked={t.is_checked || false}
                  onChange={() => handleToggleTask(t.task_id, t.is_checked || false)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className={t.is_checked ? "line-through text-gray-400" : "text-gray-700"}>
                  {t.task_title}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Truncation warning */}
      {alertsTruncated && (
        <div className="bg-amber-50 border border-amber-300 text-amber-800 text-sm rounded-lg px-4 py-3 mb-4">
          告警數量已達顯示上限 (500 筆)，部分告警未顯示。請透過匯出 CSV 查看完整紀錄，或前往歷史查詢縮小範圍。
        </div>
      )}

      {/* Daily sections */}
      <div className="space-y-4">
        {(report.daily_sections ?? []).map((section, idx) => {
          const alerts = alertsBySection[section.id] || [];
          const expanded = expandedSections.has(section.id);

          return (
            <div key={section.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              {/* Section header */}
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                aria-expanded={expanded}
              >
                <div className="flex items-center gap-3">
                  <span className={`transform transition-transform ${expanded ? "rotate-90" : ""}`}>
                    &#9654;
                  </span>
                  <span className="font-medium text-sm">
                    {weekdays[idx] || ""} — {section.section_date}
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
                </span>
              </button>

              {/* Section content */}
              {expanded && (
                <div className="px-4 pb-4 space-y-3">
                  {/* Section note */}
                  <input
                    type="text"
                    defaultValue={section.operator_name || ""}
                    onBlur={(e) => handleSectionNote(section.id, e.target.value)}
                    placeholder="當日備註 / 值班人員"
                    className="w-full text-xs px-2 py-1 border-b border-gray-100 focus:outline-none focus:border-indigo-300"
                  />

                  {alerts.length === 0 ? (
                    <div className="text-sm text-gray-400 py-4 text-center">
                      當日無 alert
                    </div>
                  ) : (
                    <div className="grid gap-3">
                      {alerts.map((a) => (
                        <AlertCard key={a.id} alert={a} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
