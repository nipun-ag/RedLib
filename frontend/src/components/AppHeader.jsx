import { formatDateLabel, formatNumber } from "@/lib/formatters"

export function AppHeader({ stats, loading, error }) {
  return (
    <header className="app-header">
      <div>
        <div className="brand-line">
          <div className="brand-mark mono">RedLib</div>
          <div className="brand-sub mono">
            Corpus-grounded adversarial prompt research workspace
          </div>
        </div>
        <h1 className="app-title">Search, inspect, and compare real jailbreak patterns.</h1>
        <p className="app-caption">
          RedLib gives trust and safety researchers direct access to a curated corpus of real
          adversarial prompts. Search mode synthesizes recurring mechanics. Browse mode exposes raw
          corpus slices without an answer layer.
        </p>
      </div>

      <div className="stats-strip" aria-label="corpus stats">
        <div className="stat-cell">
          <span className="stat-label mono">Total Prompts</span>
          <span className="stat-value mono">
            {loading ? "Loading..." : error ? "Unavailable" : formatNumber(stats.total_prompts)}
          </span>
        </div>
        <div className="stat-cell">
          <span className="stat-label mono">Sources</span>
          <span className="stat-value mono">
            {loading ? "Loading..." : error ? "Unavailable" : formatNumber(stats.total_sources)}
          </span>
        </div>
        <div className="stat-cell">
          <span className="stat-label mono">Last Sync</span>
          <span className="stat-value mono">
            {loading ? "Loading..." : error ? "Unavailable" : formatDateLabel(stats.last_sync)}
          </span>
        </div>
      </div>
    </header>
  )
}
