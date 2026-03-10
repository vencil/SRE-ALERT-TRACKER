/** Shared constants for the SRE Alert Tracker frontend. */

/** Hex colors for severity levels (charts, timelines). */
export const SEVERITY_COLORS = {
  critical: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
};

/** Tailwind CSS dot classes for severity indicators. */
export const SEVERITY_DOT_CLASS = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-400",
};

/** Chart color palette for multi-series data. */
export const CHART_COLORS = [
  "#6366f1", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899",
];
