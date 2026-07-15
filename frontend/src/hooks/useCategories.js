import { useEffect, useState } from "react"
import { API_BASE_URL } from "@/config"

export function useCategories() {
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let isMounted = true

    const loadCategories = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/categories`)
        const payload = await response.json()

        if (!response.ok) {
          throw new Error(payload.detail || "Failed to load category counts.")
        }

        if (isMounted) {
          setCategories(payload.categories || [])
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

    loadCategories()

    return () => {
      isMounted = false
    }
  }, [])

  return { categories, loading, error }
}
