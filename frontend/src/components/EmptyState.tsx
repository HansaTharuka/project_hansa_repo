/**
 * A reusable explicit empty-state message (E6-S5 AC3) — always render this
 * instead of an empty `<table>` or a blank section when a collection has no
 * items to show.
 */
interface EmptyStateProps {
  message: string;
  hint?: string;
}

export function EmptyState({ message, hint }: EmptyStateProps) {
  return (
    <div className="empty" data-testid="empty-state">
      <p>
        <strong>{message}</strong>
      </p>
      {hint !== undefined && <p>{hint}</p>}
    </div>
  );
}
