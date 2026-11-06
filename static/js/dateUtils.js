function normalizeDate(value) {
  if (value === null || value === undefined || value === "") return null;

  const direct = new Date(value);
  if (!Number.isNaN(direct.getTime())) return direct;

  const sanitized = String(value)
    .replace(/\s*[ap]\.?m\.?\s*/gi, " ")
    .replace(/\s*,\s*/g, " ")
    .replace(/\//g, "-")
    .trim();

  const fallback = new Date(sanitized);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
}

export function toUtcIso(value) {
  const date = normalizeDate(value);
  return date ? date.toISOString() : null;
}

export function formatDateParts(value) {
  const date = normalizeDate(value);
  if (!date) return { date: "—", time: "—" };

  const formatter = new Intl.DateTimeFormat("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });

  const parts = formatter.formatToParts(date);
  const values = {};
  for (const part of parts) {
    if (part.type !== "literal") values[part.type] = part.value;
  }

  const { year, month, day, hour, minute, second } = values;
  return {
    date: `${year}-${month}-${day}`,
    time: `${hour}:${minute}:${second}`,
  };
}

export function formatDateTime(value) {
  const { date, time } = formatDateParts(value);
  if (date === "—" || time === "—") return "—";
  return `${date} ${time}`;
}
