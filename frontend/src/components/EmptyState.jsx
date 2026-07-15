export function EmptyState({ title, message, loading = false }) {
  return (
    <section className="empty-panel">
      <div className="eyebrow mono">{loading ? "Loading" : "Waiting"}</div>
      <h2 className="result-technique">{title}</h2>
      <div className="panel-copy">{message}</div>
      {loading ? <div className="loading-line mono">Fetching corpus data</div> : null}
    </section>
  )
}
