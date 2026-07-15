import { useEffect, useState } from "react"

export function useCountUp(value, { duration = 850, disabled = false } = {}) {
  const [displayValue, setDisplayValue] = useState(disabled ? value : 0)

  useEffect(() => {
    if (disabled) {
      setDisplayValue(value)
      return undefined
    }

    let frameId = 0
    const startTime = performance.now()

    const tick = (timestamp) => {
      const elapsed = timestamp - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - (1 - progress) ** 4
      setDisplayValue(Math.round(value * eased))

      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick)
      }
    }

    setDisplayValue(0)
    frameId = window.requestAnimationFrame(tick)

    return () => window.cancelAnimationFrame(frameId)
  }, [duration, disabled, value])

  return displayValue
}
