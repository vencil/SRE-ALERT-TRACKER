import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchAlert, updateAlert } from "../api/client";
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

          {/* Timestamps */}
          <div className="text-xs text-gray-400 border-t border-gray-100 pt-3 flex gap-4">
            {alert.first_firing_at && <span>First: {alert.first_firing_at}</span>}
            {alert.last_firing_at && <span>Last: {alert.last_firing_at}</span>}
            {alert.created_at && <span>Created: {alert.created_at}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
