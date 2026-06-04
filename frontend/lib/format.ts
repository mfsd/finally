export function formatCurrency(value: number | null | undefined, options: Intl.NumberFormatOptions = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...options
  }).format(value);
}

export function formatCompactCurrency(value: number | null | undefined) {
  return formatCurrency(value, { notation: "compact", maximumFractionDigits: 2 });
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

export function pnlClass(value: number | null | undefined) {
  if (!value) return "text-terminal-muted";
  return value > 0 ? "text-ally-green" : "text-ally-red";
}
