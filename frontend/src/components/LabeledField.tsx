/**
 * A `label`/`input` pair associated via `for`/`id` (E2-S3 AC3) — always use
 * this instead of a bare `<input>` so every form field on the site is
 * reachable via `getByLabelText` and keyboard-navigable by construction.
 */
interface LabeledFieldProps {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
}

export function LabeledField({
  id,
  label,
  type = 'text',
  value,
  onChange,
  autoComplete,
}: LabeledFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
