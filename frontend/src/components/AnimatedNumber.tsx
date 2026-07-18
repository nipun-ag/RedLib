import { useEffect, useState } from "react"
import { useReducedMotion } from "motion/react"

import { formatNumber } from "@/lib/taxonomy"

type AnimatedNumberProps = {
  value: number | null | undefined
  className?: string
  durationMs?: number
}

export function AnimatedNumber({
  value,
  className,
  durationMs = 900,
}: AnimatedNumberProps) {
  const reducedMotion = useReducedMotion()
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (typeof value !== "number" || Number.isNaN(value)) {
      setDisplay(0)
      return
    }

    if (reducedMotion) {
      setDisplay(value)
      return
    }

    const start = performance.now()
    let frame = 0

    const tick = (now: number) => {
      const progress = Math.min((now - start) / durationMs, 1)
      const eased = 1 - (1 - progress) ** 3
      setDisplay(Math.round(value * eased))

      if (progress < 1) {
        frame = window.requestAnimationFrame(tick)
      }
    }

    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [value, durationMs, reducedMotion])

  if (typeof value !== "number" || Number.isNaN(value)) {
    return <span className={className}>—</span>
  }

  return <span className={className}>{formatNumber(display)}</span>
}
