import { formatNumber } from "@/lib/formatters"

export function TechniqueBreakdown({ breakdown }) {
  const items = Object.entries(breakdown).sort((a, b) => b[1] - a[1])

  return (
    <section className="breakdown-panel">
      <div className="eyebrow mono">Technique Mix</div>
      <ul className="breakdown-list">
        {items.map(([name, count]) => (
          <li key={name} className="breakdown-item">
            <strong>{name}</strong>
            <span className="mono">{formatNumber(count)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
