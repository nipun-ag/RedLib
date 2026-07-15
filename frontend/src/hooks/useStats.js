import { useEffect, useState } from "react"
import { API_BASE_URL } from "@/config"

const INITIAL_STATS = {
  total_prompts: 0,
  total_sources: 0,
  last_sync: "",
}

export function useStats() {
  const [stats, setStats] = useState(INITIAL_STATS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let isMounted = true

    const loadStats = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/stats`)
        const payload = await response.json()

        if (!response.ok) {
          throw new Error(payload.detail || "Failed to load corpus stats.")
        }

        if (isMounted) {
          setStats(payload)
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message)
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    loadStats()

    return () => {
      isMounted = false
    }
  }, [])

  return { stats, loading, error }
}
