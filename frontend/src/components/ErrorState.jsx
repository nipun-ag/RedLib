export function ErrorState({ title, message }) {
  return (
    <section className="error-panel">
      <div className="eyebrow mono">Connection</div>
      <h2 className="result-technique">{title}</h2>
      <div className="panel-copy">{message}</div>
    </section>
  )
}
