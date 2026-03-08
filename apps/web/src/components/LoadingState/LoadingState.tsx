type LoadingStateProps = {
  title: string;
  note?: string;
};


export function LoadingState({ title, note }: LoadingStateProps) {
  return (
    <div className="status-card">
      <div className="status-card__spinner" aria-hidden="true" />
      <div>
        <h3 className="status-card__title">{title}</h3>
        {note ? <p className="status-card__note">{note}</p> : null}
      </div>
    </div>
  );
}
