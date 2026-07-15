export function ModeExplainer({ message }) {
  return (
    <section className="explainer-bar" aria-label="mode explainer">
      <div className="eyebrow mono">Mode</div>
      <div className="explainer-copy">{message}</div>
    </section>
  )
}
