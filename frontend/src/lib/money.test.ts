import { describe, expect, it } from 'vitest';

import {
  FULL_PERCENT_BPS,
  formatBpsAsPercent,
  isExactlyFullPercent,
  parsePercentToBps,
  sumBps,
} from './money';

describe('parsePercentToBps', () => {
  it('parses a whole-number percent string into basis points', () => {
    expect(parsePercentToBps('60')).toBe(6000);
  });

  it('parses a 2-decimal-place percent string into basis points', () => {
    expect(parsePercentToBps('60.00')).toBe(6000);
  });

  it('parses a 1-decimal-place percent string, right-padding the fraction', () => {
    expect(parsePercentToBps('30.5')).toBe(3050);
  });

  it('parses the smallest representable unit, one basis point', () => {
    expect(parsePercentToBps('0.01')).toBe(1);
  });

  it('parses exactly 100.00 to 10000 basis points', () => {
    expect(parsePercentToBps('100.00')).toBe(10000);
  });

  it('parses zero', () => {
    expect(parsePercentToBps('0.00')).toBe(0);
  });

  it('tolerates surrounding whitespace', () => {
    expect(parsePercentToBps('  40.00  ')).toBe(4000);
  });

  it('returns null for an empty string', () => {
    expect(parsePercentToBps('')).toBeNull();
  });

  it('returns null for non-numeric input', () => {
    expect(parsePercentToBps('abc')).toBeNull();
  });

  it('returns null for a negative number', () => {
    expect(parsePercentToBps('-5.00')).toBeNull();
  });

  it('returns null for more than 2 decimal places', () => {
    expect(parsePercentToBps('60.001')).toBeNull();
  });

  it('never uses floating-point multiplication that could drift', () => {
    // 0.1 + 0.2 !== 0.3 under naive float math; this value would expose that
    // kind of drift if the implementation multiplied by 100 as a float.
    expect(parsePercentToBps('0.1')).toBe(10);
    expect(parsePercentToBps('0.2')).toBe(20);
  });
});

describe('sumBps', () => {
  it('sums an array of basis-point integers exactly', () => {
    expect(sumBps([6000, 3000, 1000])).toBe(10000);
  });

  it('returns 0 for an empty array', () => {
    expect(sumBps([])).toBe(0);
  });

  it('sums many small values without float drift', () => {
    const oneHundredOnePercentEntries = Array.from({ length: 100 }, () => 1);
    expect(sumBps(oneHundredOnePercentEntries)).toBe(100);
  });
});

describe('formatBpsAsPercent', () => {
  it('formats 10000 bps as "100.00"', () => {
    expect(formatBpsAsPercent(10000)).toBe('100.00');
  });

  it('formats 9000 bps as "90.00"', () => {
    expect(formatBpsAsPercent(9000)).toBe('90.00');
  });

  it('formats 0 bps as "0.00"', () => {
    expect(formatBpsAsPercent(0)).toBe('0.00');
  });

  it('formats a single basis point as "0.01"', () => {
    expect(formatBpsAsPercent(1)).toBe('0.01');
  });

  it('formats a negative value with a leading minus sign', () => {
    expect(formatBpsAsPercent(-250)).toBe('-2.50');
  });

  it('round-trips a parsed value back to its original string', () => {
    expect(formatBpsAsPercent(parsePercentToBps('42.37') as number)).toBe('42.37');
  });
});

describe('isExactlyFullPercent', () => {
  it('is true for exactly 10000 basis points', () => {
    expect(isExactlyFullPercent(FULL_PERCENT_BPS)).toBe(true);
  });

  it('is false for 9999 basis points', () => {
    expect(isExactlyFullPercent(9999)).toBe(false);
  });

  it('is false for 10001 basis points', () => {
    expect(isExactlyFullPercent(10001)).toBe(false);
  });

  it('is false for 0 basis points', () => {
    expect(isExactlyFullPercent(0)).toBe(false);
  });
});
