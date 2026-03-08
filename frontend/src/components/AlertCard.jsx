import { useState, useCallback, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { updateAlert } from "../api/client";
import SeverityBadge from "./SeverityBadge";
import LabelTagInput from "./LabelTagInput";

/**
 * Alert card — shown in ReportDetail daily sections.
 * Supports inline editing of phenomenon/impact/action_taken with debounced auto-save.
 *
 * Debounce lifecycle:
 * 1. User types → local state updates immediately (optimistic)
 * 2. After 800ms of no typing → PATCH request fires
 * 3. On success → "saved" indicator shows for 1.5s
 * 4. On unmount → pending timer is cleared (no stale saves)
 */
export default function AlertCard({ alert: initial, onUpdated }) {
  const [alert, setAlert] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const timerRef = useRef(null);
  const alertIdRef = useRef(initial.id);

  useEffect(() => {
    setAlert(initial);
    alertIdRef.current = initial.id;
  }, [initial]);

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
        const currentId = alertIdRef.current;
        setSaving(true);
        try {
          const updated = await updateAlert(currentId, { [field]: value });
          // Only update state if alert ID hasn't changed
          if (alertIdRef.current === currentId) {
            setAlert(updated);
            onUpdated?.(updated);
            setSaved(true);
            setTimeout(() => setSaved(false), 1500);
          }
        } catch (err) {
          if (alertIdRef.current === currentId) {
            setSaveError(err.message || "儲存失敗");
            setTimeout(() => setSaveError(null), 3000);
          }
        } finally {
          if (alertIdRef.current === currentId) {
            setSaving(false);
          }
        }
      }, 800);
    },
    [onUpdated],
  );

  function handleChange(field, value) {
    setAlert((prev) => ({ ...prev, [field]: value }));
    debouncedSave(field, value);
  }

  return (
    <div className="alert-card bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <SeverityBadge severity={alert.severity} />
          <Link
            to={`/alerts/${alert.id}`}
            className="font-medium text-sm text-indigo-600 hover:underline truncate"
          >
            {alert.alert_name}
          </Link>
          <span className="text-xs text-gray-500">{alert.instance}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0 text-xs text-gray-500">
          <span title="Occurrence count">x{alert.occurrence_count}</span>
          {saving && <span className="save-indicator text-amber-600">saving...</span>}
          {saved && <span className="save-indicator text-green-600">saved</span>}
          {saveError && <span className="save-indicator text-red-600">{saveError}</span>}
        </div>
      </div>

      {/* Cluster info */}
      {alert.cluster_name && (
        <div className="text-xs text-gray-500">
          Cluster: <span className="font-medium">{alert.cluster_name}</span>
        </div>
      )}

      {/* Labels */}
      <LabelTagInput
        alertId={alert.id}
        labels={alert.labels || []}
        onChange={(labels) => setAlert((prev) => ({ ...prev, labels }))}
      />

      {/* Editable fields */}
      <div className="grid gap-2">
        {[
          { field: "phenomenon", label: "現象" },
          { field: "impact", label: "影響" },
          { field: "action_taken", label: "處理作法" },
        ].map(({ field, label }) => (
          <div key={field}>
            <label className="block text-xs font-medium text-gray-500 mb-0.5">{label}</label>
            <textarea
              value={alert[field] || ""}
              onChange={(e) => handleChange(field, e.target.value)}
              placeholder={`填寫${label}...`}
              rows={1}
              className="w-full text-sm px-2 py-1.5 border border-gray-200 rounded resize-y focus:outline-none focus:ring-1 focus:ring-indigo-300 focus:border-indigo-300"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
