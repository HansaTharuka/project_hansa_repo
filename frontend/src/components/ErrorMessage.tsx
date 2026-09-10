/**
 * An inline, screen-reader-announced error banner (E2-S3 AC2).
 * `role="alert"` is what `[role=alert]` assertions in Playwright/RTL target.
 */
interface ErrorMessageProps {
  message: string;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <div className="error-message" role="alert">
      {message}
    </div>
  );
}
