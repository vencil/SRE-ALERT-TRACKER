import { useState, useEffect } from "react";
import { fetchCorrelation } from "../api/client";
import { SEVERITY_COLORS, SEVERITY_DOT_CLASS } from "../constants";

/**
 * CorrelationSection — shows co-occurring alerts grouped by time overlap.
 * Uses the most recent week from trend data to auto-select year/week.
 */
export default function CorrelationSection({ trends }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState(null);
  const [expandedGroup, setExpandedGroup] = useState(null);

  // Extract available weeks from trends
  const weekOptions = trends.map((t) => t.week).reverse();

  // Derive effective week: user selection or auto-select first available
  const effectiveWeek = selectedWeek ?? (weekOptions.length > 0 ? weekOptions[0] : null);

  useEffect(() => {
    if (!effectiveWeek) return;
    const match = effectiveWeek.match(/^(\d{4})-W(\d{2})$/);
    if (!match) return;
    let cancelled = false;
    setLoading(true); // eslint-disable-line react-hooks/set-state-in-effect -- loading flag before async fetch is standard React
    fetchCorrelation({ year: parseInt(match[1], 10), week: parseInt(match[2], 10) })
      .then((data) => { if (!cancelled) setGroups(data.groups ?? []); })
      .catch(() => { if (!cancelled) setGroups([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [effectiveWeek]);

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">Alert 關聯分析</h2>
        {weekOptions.length > 0 && (
          <select
            value={effectiveWeek || ""}
            onChange={(e) => setSelectedWeek(e.target.value)}
            className="text-sm px-2 py-1.5 border border-gray-200 rounded"
          >
            {weekOptions.map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <div className="text-sm text-gray-400 py-8 text-center">分析中...</div>
      ) : groups.length === 0 ? (
        <div className="text-sm text-gray-400 py-8 text-center">
          本週無同時段重疊的 alert 群組
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group, gi) => (
            <div
              key={gi}
              className="border border-gray-100 rounded-lg overflow-hidden"
            >
              <button
                onClick={() => setExpandedGroup(expandedGroup === gi ? null : gi)}
                className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
              >
                <div className="flex items-center gap-3">
                  <span className={`transform transition-transform text-xs ${expandedGroup === gi ? "rotate-90" : ""}`}>
                    &#9654;
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {group.alert_count} alerts 重疊
                  </span>
                  <span className="text-xs text-gray-400">
                    {group.window_start?.slice(11, 16)} ~ {group.window_end?.slice(11, 16)}
                  </span>
                </div>
                <div className="flex gap-1">
                  {group.alerts.slice(0, 5).map((a, ai) => (
                    <span
                      key={ai}
                      className={`w-2 h-2 rounded-full ${SEVERITY_DOT_CLASS[a.severity] || "bg-gray-400"}`}
                      title={a.alert_name}
                    />
                  ))}
                  {group.alerts.length > 5 && (
                    <span className="text-xs text-gray-400">+{group.alerts.length - 5}</span>
                  )}
                </div>
              </button>

              {expandedGroup === gi && (
                <div className="px-4 pb-3">
                  {/* Mini timeline: horizontal bars showing overlap */}
                  <div className="mb-3 relative" style={{ minHeight: group.alerts.length * 28 + 20 }}>
                    <TimelineView alerts={group.alerts} windowStart={group.window_start} windowEnd={group.window_end} />
                  </div>

                  {/* Alert list */}
                  <div className="grid gap-1.5">
                    {group.alerts.map((a) => (
                      <div key={a.id} className="flex items-center justify-between text-xs px-2 py-1.5 bg-gray-50 rounded">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${SEVERITY_DOT_CLASS[a.severity] || "bg-gray-400"}`} />
                          <span className="font-medium text-gray-800">{a.alert_name}</span>
                          {a.cluster_name && (
                            <span className="text-gray-400">{a.cluster_name}</span>
                          )}
                        </div>
                        <span className="text-gray-400">
                          {a.first_firing_at?.slice(11, 16)} ~ {a.last_firing_at?.slice(11, 16)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}


/**
 * TimelineView — mini Gantt-style bars showing alert time overlaps.
 */
function TimelineView({ alerts, windowStart, windowEnd }) {
  const start = new Date(windowStart).getTime();
  const end = new Date(windowEnd).getTime();
  const range = Math.max(end - start, 1);

  return (
    <div className="relative border-l border-gray-200 ml-2">
      {/* Time axis labels */}
      <div className="flex justify-between text-xs text-gray-400 pl-2 mb-1">
        <span>{windowStart?.slice(11, 16)}</span>
        <span>{windowEnd?.slice(11, 16)}</span>
      </div>

      {alerts.map((a) => {
        const aStart = new Date(a.first_firing_at).getTime();
        const aEnd = new Date(a.last_firing_at).getTime();
        const leftPct = Math.max(0, ((aStart - start) / range) * 100);
        const widthPct = Math.max(1, ((aEnd - aStart) / range) * 100);
        const color = SEVERITY_COLORS[a.severity] || "#6b7280";

        return (
          <div key={a.id} className="flex items-center h-6 pl-2" title={`${a.alert_name} (${a.first_firing_at?.slice(11, 16)} ~ ${a.last_firing_at?.slice(11, 16)})`}>
            <div className="relative w-full h-3">
              <div
                className="absolute h-3 rounded-sm opacity-80"
                style={{
                  left: `${leftPct}%`,
                  width: `${Math.min(widthPct, 100 - leftPct)}%`,
                  backgroundColor: color,
                  minWidth: "4px",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
