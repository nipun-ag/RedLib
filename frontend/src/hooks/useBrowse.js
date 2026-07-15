import { useState } from "react"
import { API_BASE_URL } from "@/config"

const INITIAL_BROWSE_DATA = {
  results: [],
  next_cursor: null,
  total: 0,
  category: "",
}

export function useBrowse() {
  const [data, setData] = useState(INITIAL_BROWSE_DATA)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const loadFirstPage = async (category) => {
    if (!category) {
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/browse?category=${encodeURIComponent(category)}&limit=20`
      )
      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload.detail || "Failed to browse category prompts.")
      }

      setData(payload)
    } catch (requestError) {
      setError(requestError.message)
      setData(INITIAL_BROWSE_DATA)
    } finally {
      setLoading(false)
    }
  }

  const loadNextPage = async () => {
    if (!data.category || !data.next_cursor) {
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/browse?category=${encodeURIComponent(data.category)}&cursor=${encodeURIComponent(data.next_cursor)}&limit=20`
      )
      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load the next browse page.")
      }

      setData((current) => ({
        ...payload,
        results: [...current.results, ...payload.results],
      }))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return {
    data,
    loading,
    error,
    loadFirstPage,
    loadNextPage,
  }
}
