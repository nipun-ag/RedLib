export function SummaryPanel({ answer }) {
  return (
    <section className="summary-panel">
      <div className="eyebrow mono">AI Summary</div>
      <div className="summary-text">{answer}</div>
    </section>
  )
}
