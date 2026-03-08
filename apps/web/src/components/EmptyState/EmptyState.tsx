type EmptyStateProps = {
  title: string;
  note: string;
  tone?: "empty" | "error";
};


export function EmptyState({ title, note, tone = "empty" }: EmptyStateProps) {
  return (
    <div className={`status-card status-card--${tone}`}>
      <div className="status-card__glyph" aria-hidden="true">
        {tone === "error" ? "!" : "·"}
      </div>
      <div>
        <h3 className="status-card__title">{title}</h3>
        <p className="status-card__note">{note}</p>
      </div>
    </div>
  );
}
