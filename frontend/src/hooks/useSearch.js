import { useState } from "react"
import { API_BASE_URL } from "@/config"

const INITIAL_SEARCH_DATA = {
  answer: "",
  results: [],
  technique_breakdown: {},
  result_count: 0,
}

export function useSearch() {
  const [data, setData] = useState(INITIAL_SEARCH_DATA)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const runSearch = async (query, categoryFilter) => {
    setLoading(true)
    setError("")

    try {
      const response = await fetch(`${API_BASE_URL}/api/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query,
          category_filter: categoryFilter,
        }),
      })

      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload.detail || "Search request failed.")
      }

      setData(payload)
    } catch (requestError) {
      setError(requestError.message)
      setData(INITIAL_SEARCH_DATA)
    } finally {
      setLoading(false)
    }
  }

  return {
    data,
    loading,
    error,
    runSearch,
  }
}
