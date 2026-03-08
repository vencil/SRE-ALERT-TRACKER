import { useState, useEffect, useRef, useMemo } from "react";
import { fetchLabels, addAlertLabel, removeAlertLabel } from "../api/client";
import LabelTag from "./LabelTag";

/**
 * Autocomplete label tag input for alert records.
 * Shows existing labels as tags, with a dropdown to add more.
 */
export default function LabelTagInput({ alertId, labels: initialLabels, onChange }) {
  const [labels, setLabels] = useState(initialLabels || []);
  const [allLabels, setAllLabels] = useState([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const wrapperRef = useRef(null);

  // Load all available labels once
  useEffect(() => {
    fetchLabels()
      .then((data) => setAllLabels(data.labels ?? data ?? []))
      .catch(() => {});
  }, []);

  // Sync when parent changes
  useEffect(() => {
    setLabels(initialLabels || []);
  }, [initialLabels]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useMemo(() => {
    const currentIds = new Set(labels.map((l) => l.id));
    return allLabels.filter(
      (l) => !currentIds.has(l.id) && l.name.toLowerCase().includes(query.toLowerCase()),
    );
  }, [labels, allLabels, query]);

  async function handleAdd(labelId) {
    setError(null);
    try {
      const updated = await addAlertLabel(alertId, labelId);
      const newLabels = updated.labels ?? labels;
      setLabels(newLabels);
      onChange?.(newLabels);
      setQuery("");
      setOpen(false);
    } catch (err) {
      setError(err.message || "新增 label 失敗");
      setTimeout(() => setError(null), 3000);
    }
  }

  async function handleRemove(labelId) {
    setError(null);
    try {
      const updated = await removeAlertLabel(alertId, labelId);
      const newLabels = updated.labels ?? labels.filter((l) => l.id !== labelId);
      setLabels(newLabels);
      onChange?.(newLabels);
    } catch (err) {
      setError(err.message || "移除 label 失敗");
      setTimeout(() => setError(null), 3000);
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <div className="flex flex-wrap items-center gap-1">
        {labels.map((l) => (
          <LabelTag key={l.id} label={l} onRemove={handleRemove} />
        ))}
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="+ label"
          className="text-xs px-1.5 py-0.5 border border-dashed border-gray-300 rounded w-20 focus:outline-none focus:border-indigo-400"
        />
      </div>
      {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
      {open && filtered.length > 0 && (
        <ul className="absolute z-20 mt-1 bg-white border border-gray-200 rounded shadow-lg max-h-40 overflow-y-auto w-48">
          {filtered.slice(0, 20).map((l) => (
            <li
              key={l.id}
              onClick={() => handleAdd(l.id)}
              className="px-3 py-1.5 text-sm cursor-pointer hover:bg-indigo-50 flex items-center gap-2"
            >
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: l.color || "#6b7280" }}
              />
              {l.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
