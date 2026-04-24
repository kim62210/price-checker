import { describe, expect, it } from "vitest";

import {
  formatCompactNumber,
  formatCurrencyKRW,
  formatInteger,
  formatPercent,
  toNumber,
} from "./format";

describe("format", () => {
  it("formats KRW currency with locale prefix", () => {
    expect(formatCurrencyKRW("ko", 1234567)).toContain("1,234,567");
    expect(formatCurrencyKRW("en", 1234567)).toContain("1,234,567");
  });

  it("formats compact numbers", () => {
    expect(formatCompactNumber("en", 1500)).toBe("1.5K");
  });

  it("formats integer with thousands separator", () => {
    expect(formatInteger("ko", 9876)).toBe("9,876");
  });

  it("formats percent 0-1 scale", () => {
    expect(formatPercent("en", 0.975)).toBe("97.5%");
  });

  it("toNumber handles decimal strings and falls back to 0", () => {
    expect(toNumber("1234.5")).toBe(1234.5);
    expect(toNumber(null)).toBe(0);
    expect(toNumber("not-a-number")).toBe(0);
  });
});
