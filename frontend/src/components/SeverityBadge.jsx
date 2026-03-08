const colorMap = {
  critical: "bg-red-100 text-red-800 border-red-200",
  warning: "bg-amber-100 text-amber-800 border-amber-200",
  info: "bg-blue-100 text-blue-800 border-blue-200",
};

export default function SeverityBadge({ severity }) {
  const cls = colorMap[severity] || "bg-gray-100 text-gray-700 border-gray-200";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded border ${cls}`}>
      {severity}
    </span>
  );
}
