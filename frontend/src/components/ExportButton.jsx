import { exportReportUrl } from "../api/client";

/**
 * Export button — triggers download of report data in CSV or JSON format.
 */
export default function ExportButton({ reportId }) {
  return (
    <div className="flex gap-1">
      <a
        href={exportReportUrl(reportId, "csv")}
        download
        className="px-3 py-1.5 text-xs bg-gray-100 rounded hover:bg-gray-200 transition-colors"
      >
        CSV
      </a>
      <a
        href={exportReportUrl(reportId, "json")}
        download
        className="px-3 py-1.5 text-xs bg-gray-100 rounded hover:bg-gray-200 transition-colors"
      >
        JSON
      </a>
    </div>
  );
}
