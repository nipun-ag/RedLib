/** API base: empty in local Vite (proxied); production hits the live API. */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "" : "https://api-redlib.bynipun.com")

export type ConfidenceLevel = "HIGH" | "MED" | "LOW"

export type PromptResult = {
  id: string
  prompt_excerpt: string
  technique: string
  source: string
  confidence?: ConfidenceLevel
  confidence_score?: number
}

export type StatsResponse = {
  total_prompts: number
  total_sources: number
  last_sync: string
}

export type CategoryItem = {
  name: string
  count: number
  icon: string
}

export type CategoriesResponse = {
  categories: CategoryItem[]
}

export type QueryResponse = {
  answer: string
  results: PromptResult[]
  technique_breakdown: Record<string, number>
  result_count: number
  query_type: "semantic"
}

export type BrowseResponse = {
  results: PromptResult[]
  next_cursor: string | null
  total: number
  category: string
}

export type PromptDetailResponse = {
  id: string
  full_prompt: string
  technique: string
  source: string
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function fetchJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { headers: optionHeaders, signal, ...restOptions } = options
  const headers = new Headers(optionHeaders)

  if (restOptions.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...restOptions,
    headers,
    signal,
  })

  if (!response.ok) {
    let message = "Request failed"

    try {
      const body = (await response.json()) as { detail?: string }
      message = body.detail || message
    } catch {
      // Keep fallback message.
    }

    throw new ApiError(message, response.status)
  }

  return response.json() as Promise<T>
}

export function getStats(signal?: AbortSignal): Promise<StatsResponse> {
  return fetchJson<StatsResponse>("/api/stats", { signal })
}

export function getCategories(
  signal?: AbortSignal,
): Promise<CategoriesResponse> {
  return fetchJson<CategoriesResponse>("/api/categories", { signal })
}

export function queryCorpus(
  query: string,
  categoryFilter: string | null,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  return fetchJson<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify({
      query,
      category_filter: categoryFilter,
    }),
    signal,
  })
}

export function browseCategory(
  category: string,
  cursor: string | null = null,
  limit = 20,
  signal?: AbortSignal,
): Promise<BrowseResponse> {
  const params = new URLSearchParams({
    category,
    limit: String(limit),
  })

  if (cursor) {
    params.set("cursor", cursor)
  }

  return fetchJson<BrowseResponse>(`/api/browse?${params.toString()}`, {
    signal,
  })
}

export function getPrompt(
  promptId: string,
  signal?: AbortSignal,
): Promise<PromptDetailResponse> {
  return fetchJson<PromptDetailResponse>(
    `/api/prompts/${encodeURIComponent(promptId)}`,
    { signal },
  )
}
