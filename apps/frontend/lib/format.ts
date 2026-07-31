export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "—"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(date)
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) {
    return "—"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000)
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" })
  const ranges: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ]
  for (const [unit, seconds] of ranges) {
    const value = diffSeconds / seconds
    if (Math.abs(value) >= 1 || unit === "second") {
      return formatter.format(Math.round(value), unit)
    }
  }
  return "just now"
}

export function getInitials(email: string | null | undefined): string {
  if (!email) {
    return "?"
  }
  const local = email.split("@")[0] ?? "?"
  const parts = local.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) {
    return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase()
  }
  return (local[0] ?? "?").toUpperCase()
}
