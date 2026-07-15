import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { API_BASE_URL } from "../config";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }

  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDateLabel(value) {
  if (!value) {
    return "--";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

export async function fetchJson(path, options = {}) {
  const { headers, ...restOptions } = options;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
    ...restOptions,
  });

  if (!response.ok) {
    let detail = "Request failed";

    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Ignore JSON parse failures and use the default message.
    }

    throw new Error(detail);
  }

  return response.json();
}
