import { useCountUp } from "@/hooks/useCountUp"

export function CountUpValue({ value, loading }) {
  const displayValue = useCountUp(value, { disabled: loading })

  if (loading) {
    return "..."
  }

  return displayValue.toLocaleString("en-US")
}
