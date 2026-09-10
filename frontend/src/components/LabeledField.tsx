/**
 * A `label`/`input` pair associated via `for`/`id` (E2-S3 AC3) — always use
 * this instead of a bare `<input>` so every form field on the site is
 * reachable via `getByLabelText` and keyboard-navigable by construction.
 *
 * `error` (E7-S5 AC2) is optional and additive: when present it renders an
 * inline, screen-reader-announced message tied to the input via
 * `aria-describedby`/`aria-invalid`. Existing callers that never pass it are
 * unaffected.
 */
interface LabeledFieldProps {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  error?: string;
  min?: string;
  step?: string;
}

export function LabeledField({
  id,
  label,
  type = 'text',
  value,
  onChange,
  autoComplete,
  error,
  min,
  step,
}: LabeledFieldProps) {
  const errorId = `${id}-error`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        min={min}
        step={step}
        aria-invalid={error !== undefined ? true : undefined}
        aria-describedby={error !== undefined ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error !== undefined && (
        <p className="err" role="alert" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}
