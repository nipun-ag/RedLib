import { useEffect, useState } from "react"

const STORAGE_KEY = "redlib_responsible_use_accepted"

export function useResponsibleGate() {
  const [accepted, setAccepted] = useState(false)

  useEffect(() => {
    setAccepted(window.sessionStorage.getItem(STORAGE_KEY) === "true")
  }, [])

  const accept = () => {
    window.sessionStorage.setItem(STORAGE_KEY, "true")
    setAccepted(true)
  }

  return { accepted, accept }
}
