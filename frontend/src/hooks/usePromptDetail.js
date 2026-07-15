import { useState } from "react"
import { API_BASE_URL } from "@/config"

export function usePromptDetail() {
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [prompt, setPrompt] = useState(null)

  const openPrompt = async (promptId) => {
    setIsOpen(true)
    setLoading(true)
    setError("")
    setPrompt(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/prompts/${encodeURIComponent(promptId)}`)
      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load the full prompt.")
      }

      setPrompt(payload)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const closePrompt = () => {
    setIsOpen(false)
    setLoading(false)
    setError("")
    setPrompt(null)
  }

  return {
    isOpen,
    loading,
    error,
    prompt,
    openPrompt,
    closePrompt,
  }
}
