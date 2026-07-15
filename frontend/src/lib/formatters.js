export function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US")
}

export function formatDateLabel(value) {
  if (!value) {
    return "Unavailable"
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function confidenceClassName(confidence) {
  const normalized = String(confidence || "").toLowerCase()
  return normalized ? `is-${normalized}` : ""
}
