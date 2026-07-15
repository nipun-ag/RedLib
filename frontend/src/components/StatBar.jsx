import CountUpNumber from "./CountUpNumber";
import { formatDateLabel } from "../lib/utils";

export default function StatBar({ stats, loading, error }) {
  const items = [
    {
      label: "Total Prompts",
      value: stats?.total_prompts ?? 0,
      glow: true,
      formatter: null,
    },
    {
      label: "Sources",
      value: stats?.total_sources ?? 0,
      glow: false,
      formatter: null,
    },
    {
      label: "Last Sync",
      value: stats?.last_sync ?? "",
      glow: false,
      formatter: formatDateLabel,
    },
  ];

  return (
    <section className="stat-bar" aria-label="Corpus statistics">
      {items.map((item) => (
        <div className={`stat-card${item.glow ? " stat-card-glow" : ""}`} key={item.label}>
          <div className="stat-value">
            {loading ? (
              <span className="skeleton-line stat-skeleton" />
            ) : item.formatter ? (
              item.formatter(item.value)
            ) : (
              <CountUpNumber value={item.value} />
            )}
          </div>
          <div className="stat-label">{item.label}</div>
        </div>
      ))}

      {error ? <p className="status-text status-error">{error}</p> : null}
    </section>
  );
}
