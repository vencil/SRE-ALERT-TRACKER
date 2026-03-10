import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchAlert, updateAlert, fetchAlertHistory, fetchAlertSuggestion, fetchHealth } from "../api/client";
import SeverityBadge from "../components/SeverityBadge";
import LabelTagInput from "../components/LabelTagInput";

/**
 * Alert 明細頁 — full view of a single alert record.
 * Auto fields are read-only with an unlock escape hatch.
 * Manual fields (phenomenon, impact, action_taken) are directly editable.
 */
export default function AlertDetail() {
  const { id } = useParams();
  const [alert, setAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editLocked, setEditLocked] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const timerRef = useRef(null);
  const idRef = useRef(id);

  useEffect(() => {
    idRef.current = id;
    fetchAlert(id)
      .then(setAlert)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const debouncedSave = useCallback(
    (field, value) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      setSaveError(null);
      timerRef.current = setTimeout(async () => {
        const currentId = idRef.current;
        setSaving(true);
        try {
          const updated = await updateAlert(currentId, { [field]: value });
          if (idRef.current === currentId) {
            setAlert(updated);
            setSaved(true);
            setTimeout(() => setSaved(false), 1500);
          }
        } catch (err) {
          if (idRef.current === currentId) {
            setSaveError(err.message || "儲存失敗");
            setTimeout(() => setSaveError(null), 3000);
          }
        } finally {
          if (idRef.current === currentId) {
            setSaving(false);
          }
        }
      }, 800);
    },
    [],
  );

  function handleFieldChange(field, value) {
    setAlert((prev) => ({ ...prev, [field]: value }));
    debouncedSave(field, value);
  }

  if (loading) return <div className="text-center py-12 text-gray-500">載入中...</div>;
  if (error) return <div className="text-center py-12 text-red-600">{error}</div>;
  if (!alert) return <div className="text-center py-12 text-gray-400">找不到 Alert</div>;

  const autoFields = [
    { key: "alert_name", label: "Alert Name" },
    { key: "severity", label: "Severity" },
    { key: "instance", label: "Instance" },
    { key: "fingerprint", label: "Fingerprint" },
    { key: "cluster_name", label: "Cluster" },
    { key: "occurrence_count", label: "發生次數" },
  ];

  const manualFields = [
    { key: "phenomenon", label: "現象" },
    { key: "impact", label: "影響" },
    { key: "action_taken", label: "處理作法" },
  ];

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="text-sm text-indigo-600 hover:underline">
        &larr; 返回
      </Link>

      <div className="mt-3 bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SeverityBadge severity={alert.severity} />
            <h1 className="text-lg font-bold text-gray-900">{alert.alert_name}</h1>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            {saving && <span className="text-amber-600">saving...</span>}
            {saved && <span className="text-green-600">saved</span>}
            {saveError && <span className="text-red-600">{saveError}</span>}
            {alert.manually_edited && (
              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded">手動編輯過</span>
            )}
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Auto fields */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700">自動欄位</h2>
              <button
                type="button"
                onClick={() => setEditLocked(!editLocked)}
                className="text-xs text-gray-400 hover:text-indigo-600"
                title={editLocked ? "解鎖編輯" : "鎖定"}
              >
                {editLocked ? "🔒 解鎖" : "🔓 鎖定"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {autoFields.map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
                  {editLocked ? (
                    <div className="text-sm text-gray-900 bg-gray-50 px-2 py-1.5 rounded">
                      {alert[key] ?? "—"}
                    </div>
                  ) : (
                    <input
                      type="text"
                      value={alert[key] ?? ""}
                      onChange={(e) => handleFieldChange(key, e.target.value)}
                      className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Labels */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Labels</h2>
            <LabelTagInput
              key={alert.id}
              alertId={alert.id}
              labels={alert.labels || []}
              onChange={(labels) => setAlert((prev) => ({ ...prev, labels }))}
            />
          </div>

          {/* Manual fields */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">處理紀錄</h2>
            <div className="grid gap-3">
              {manualFields.map(({ key, label }) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
                  <textarea
                    value={alert[key] || ""}
                    onChange={(e) => handleFieldChange(key, e.target.value)}
                    placeholder={`填寫${label}...`}
                    rows={3}
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300 resize-y"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* AI Suggestion */}
          <AISuggestionSection
            alertId={alert.id}
            onApply={(text) => handleFieldChange("action_taken", text)}
          />

          {/* Timestamps */}
          <div className="text-xs text-gray-400 border-t border-gray-100 pt-3 flex gap-4">
            {alert.first_firing_at && <span>First: {alert.first_firing_at}</span>}
            {alert.last_firing_at && <span>Last: {alert.last_firing_at}</span>}
            {alert.created_at && <span>Created: {alert.created_at}</span>}
          </div>
        </div>
      </div>

      {/* History Section */}
      <HistorySection alertId={id} />
    </div>
  );
}


/**
 * AISuggestionSection — optional LLM-powered handling suggestion.
 * Only visible when the backend reports llm_enabled = true.
 */
function AISuggestionSection({ alertId, onApply }) {
  const [enabled, setEnabled] = useState(null); // null = loading, true/false
  const [suggestion, setSuggestion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check if LLM feature is enabled
  useEffect(() => {
    fetchHealth()
      .then((data) => setEnabled(data.features?.llm_enabled ?? false))
      .catch(() => setEnabled(false));
  }, []);

  if (enabled === null || enabled === false) return null;

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setSuggestion(null);
    try {
      const data = await fetchAlertSuggestion(alertId);
      setSuggestion(data.suggestion);
    } catch (err) {
      setError(err.message || "AI 建議生成失敗");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-700">AI 處理建議</h2>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={loading}
          className="text-xs px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded hover:bg-indigo-100 disabled:opacity-50 transition-colors"
        >
          {loading ? "生成中..." : suggestion ? "重新生成" : "生成建議"}
        </button>
      </div>

      {loading && (
        <div className="space-y-2 animate-pulse">
          <div className="h-3 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-1/2" />
          <div className="h-3 bg-gray-200 rounded w-2/3" />
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>
      )}

      {suggestion && !loading && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
          <p className="text-sm text-gray-800 whitespace-pre-wrap mb-2">{suggestion}</p>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">
              AI 生成的草稿，套用前請務必確認符合現況。
            </span>
            <button
              type="button"
              onClick={() => onApply(suggestion)}
              className="text-xs px-2.5 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors"
            >
              套用至處理作法
            </button>
          </div>
        </div>
      )}

      {!suggestion && !loading && !error && (
        <p className="text-xs text-gray-400">
          點擊「生成建議」，AI 將根據 alert 資訊與歷史處理紀錄提供建議。
        </p>
      )}
    </div>
  );
}


/**
 * HistorySection — shows past records for the same alert (fingerprint-first, then alert_name).
 * Only displays records where action_taken has been filled.
 */
function HistorySection({ alertId }) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (!alertId) return;
    let cancelled = false;
    fetchAlertHistory(alertId)
      .then((data) => { if (!cancelled) setHistory(data); })
      .catch(() => { if (!cancelled) setHistory(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [alertId]);

  if (loading) return null;
  if (!history || history.total === 0) {
    return (
      <div className="mt-4 bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-gray-700">歷史紀錄</h2>
        <p className="text-sm text-gray-400 mt-2">此 alert 首次出現，無歷史處理紀錄可參考。</p>
      </div>
    );
  }

  return (
    <div className="mt-4 bg-white border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <h2 className="text-sm font-semibold text-gray-700">
          歷史紀錄 ({history.total})
        </h2>
        <span className={`text-gray-400 transform transition-transform ${expanded ? "rotate-90" : ""}`}>
          &#9654;
        </span>
      </button>

      {expanded && (
        <div className="px-5 pb-4 space-y-3">
          {history.records.map((r) => (
            <div
              key={r.id}
              className="border border-gray-100 rounded-lg p-3 text-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">
                    {r.year}-W{String(r.week_number).padStart(2, "0")}
                  </span>
                  <span className="text-xs text-gray-400">{r.section_date}</span>
                  {r.match_type === "fingerprint" ? (
                    <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 rounded">
                      精準
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded">
                      同名
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  {r.cluster_name && <span>{r.cluster_name}</span>}
                  {r.operator_name && <span>值班: {r.operator_name}</span>}
                  <span>x{r.occurrence_count}</span>
                </div>
              </div>

              {r.action_taken && (
                <div className="mb-1">
                  <span className="text-xs text-gray-500">處理作法：</span>
                  <p className="text-gray-800 whitespace-pre-wrap">{r.action_taken}</p>
                </div>
              )}
              {r.phenomenon && (
                <div className="mb-1">
                  <span className="text-xs text-gray-500">現象：</span>
                  <span className="text-gray-600">{r.phenomenon}</span>
                </div>
              )}
              {r.impact && (
                <div>
                  <span className="text-xs text-gray-500">影響：</span>
                  <span className="text-gray-600">{r.impact}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
