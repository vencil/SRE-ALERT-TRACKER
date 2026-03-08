export default function LabelTag({ label, onRemove }) {
  const bg = label.color || "#6b7280";
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-white"
      style={{ backgroundColor: bg }}
    >
      {label.name}
      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(label.id)}
          className="ml-0.5 hover:text-gray-200 text-white/80"
          aria-label={`Remove label ${label.name}`}
        >
          &times;
        </button>
      )}
    </span>
  );
}
