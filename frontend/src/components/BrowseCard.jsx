export default function BrowseCard({ result, onViewPrompt }) {
  return (
    <article className="result-card">
      <div className="result-meta-row">
        <div className="result-meta-left">
          <span className="technique-tag">{result.technique}</span>
        </div>

        <span className="result-source">{result.source}</span>
      </div>

      <p className="result-excerpt">{result.prompt_excerpt}</p>

      <button className="prompt-link" type="button" onClick={() => onViewPrompt(result.id)}>
        View Full Prompt →
      </button>
    </article>
  );
}
