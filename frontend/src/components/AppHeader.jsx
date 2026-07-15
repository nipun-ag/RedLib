import { formatDateLabel, formatNumber } from "@/lib/formatters"

export function AppHeader({ stats, loading, error }) {
  const isPending = loading || Boolean(error)

  return (
    <header className="app-header">
      <div className="app-header-copy">
        <div className="brand-line">
          <div className="brand-mark mono">RedLib</div>
          <div className="brand-sub mono">React research interface</div>
        </div>
        <h1 className="app-title">Jailbreak Corpus Search</h1>
      </div>

      <div className="stats-strip" aria-label="corpus stats">
        <div className="stat-cell">
          <span className="stat-label mono">Total Prompts</span>
          <span className={`stat-value mono${isPending ? " is-pending" : ""}`}>
            {loading ? "..." : error ? "—" : formatNumber(stats.total_prompts)}
          </span>
        </div>
        <div className="stat-cell">
          <span className="stat-label mono">Sources</span>
          <span className={`stat-value mono${isPending ? " is-pending" : ""}`}>
            {loading ? "..." : error ? "—" : formatNumber(stats.total_sources)}
          </span>
        </div>
        <div className="stat-cell">
          <span className="stat-label mono">Last Sync</span>
          <span className={`stat-value mono${isPending ? " is-pending" : ""}`}>
            {loading ? "..." : formatDateLabel(stats.last_sync, { pending: Boolean(error) })}
          </span>
        </div>
      </div>
    </header>
  )
}
