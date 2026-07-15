export default function AISummaryCard({ answer }) {
  return (
    <section className="ai-summary-card">
      <div className="ai-summary-label">AI Summary</div>
      <p className="ai-summary-text">{answer}</p>
    </section>
  );
}
