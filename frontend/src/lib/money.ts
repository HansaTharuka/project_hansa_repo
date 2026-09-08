/**
 * Basis-point-safe money/percent arithmetic helpers (E10-S4; NFR-01).
 *
 * WealthWise's fixed-point convention: money and percent values cross the API
 * as 2-decimal-place strings (e.g. "60.00"), never JSON numbers, because a
 * JSON number round-trips through an IEEE-754 double and can drift
 * (data-models.md §2). Display-only screens (e.g. Holdings.tsx) render those
 * strings verbatim and need nothing more.
 *
 * The allocation template editor is different: it must *sum* several
 * entered percent strings into a running total and gate Publish on that sum
 * being exactly 100.00. Doing that with `parseFloat` + float addition would
 * reintroduce the exact drift NFR-01 forbids (e.g. 0.1 + 0.2 !== 0.3 in
 * IEEE-754). The only safe representation for that arithmetic is an integer
 * count of basis points, added with plain integer addition.
 *
 * Basis-point convention: 1.00% == 100 bps, so 100.00% == 10000 bps. This is
 * the SAME convention as the backend's authoritative sum-to-100 gate
 * (`ALLOCATION_TOTAL_BPS = 10000` in backend/src/domain/admin/service.py)
 * and the `AllocationEntry.percent_bps` field it operates on
 * (frontend/src/types/entities.ts, data-models.md §4.6). This file must
 * never define an independently-tunable threshold — it is a UX convenience
 * gate in front of the same backend rule (architecture_check
 * `template_editor_sum_gate_matches_api`).
 */

/** Basis points per whole percentage point: 1.00% == 100 bps. */
export const PERCENT_BPS_SCALE = 100;

/** 100.00% expressed in basis points — the exact target the template
 * editor's Publish gate compares against, with no tolerance (AC-02, NFR-08). */
export const FULL_PERCENT_BPS = 10000;

/** A non-negative decimal number string with at most 2 decimal places. */
const PERCENT_STRING_PATTERN = /^\d+(\.\d{1,2})?$/;

/**
 * Parse a decimal percent string (e.g. "60", "60.00", "30.5") into an
 * integer basis-point value (e.g. 6000, 6000, 3050).
 *
 * Returns `null` for any input that is not a non-negative decimal number
 * with at most 2 decimal places — callers decide how to treat an
 * unparseable entry (the template editor treats it as blocking Publish).
 *
 * Deliberately never uses `parseFloat` followed by multiplication: that
 * round-trips the value through an IEEE-754 double and can silently drift.
 * Instead this splits the validated string into its integer and fractional
 * parts and combines them with exact integer arithmetic.
 */
export function parsePercentToBps(value: string): number | null {
  const trimmed = value.trim();
  if (!PERCENT_STRING_PATTERN.test(trimmed)) {
    return null;
  }
  const parts = trimmed.split('.');
  const wholePart = parts[0] ?? '';
  const fractionPart = parts[1] ?? '';
  const paddedFraction = fractionPart.padEnd(2, '0');
  const whole = Number.parseInt(wholePart, 10);
  const fraction = Number.parseInt(paddedFraction, 10);
  return whole * PERCENT_BPS_SCALE + fraction;
}

/**
 * Sum an array of integer basis-point values with plain integer addition.
 * Integers are represented exactly in IEEE-754 doubles up to 2^53, so this
 * never drifts the way summing the original decimal strings as floats would.
 */
export function sumBps(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

/**
 * Format an integer basis-point value back to a 2-decimal-place percent
 * string (e.g. 9000 -> "90.00", 10000 -> "100.00", 1 -> "0.01").
 */
export function formatBpsAsPercent(bps: number): string {
  const sign = bps < 0 ? '-' : '';
  const absolute = Math.abs(bps);
  const whole = Math.floor(absolute / PERCENT_BPS_SCALE);
  const fraction = absolute % PERCENT_BPS_SCALE;
  return `${sign}${whole}.${String(fraction).padStart(2, '0')}`;
}

/**
 * True only when `bps` is exactly `FULL_PERCENT_BPS` (100.00%) — no
 * tolerance window, matching the backend's exact-equality check (AC-02,
 * NFR-08).
 */
export function isExactlyFullPercent(bps: number): boolean {
  return bps === FULL_PERCENT_BPS;
}
