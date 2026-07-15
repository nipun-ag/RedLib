export function ModeExplainer({ title, body, meta }) {
  return (
    <section className="explainer-bar" aria-label="mode explainer">
      <div>
        <div className="eyebrow mono">Mode Explainer</div>
        <h2 className="result-technique">{title}</h2>
        <div className="explainer-copy">{body}</div>
      </div>
      <div className="explainer-meta mono">{meta}</div>
    </section>
  )
}
