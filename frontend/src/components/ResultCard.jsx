import { confidenceClassName } from "@/lib/formatters"

export function ResultCard({ mode, result, onViewFullPrompt }) {
  return (
    <article className="result-card">
      <div className="result-topline">
        <span className="result-id mono">Prompt ID {result.id}</span>
        {mode === "search" ? (
          <span className={`confidence-tag mono ${confidenceClassName(result.confidence)}`}>
            {result.confidence} confidence
          </span>
        ) : null}
      </div>

      <h3 className="result-technique">{result.technique}</h3>
      <p className="result-excerpt">{result.prompt_excerpt}</p>

      <div className="result-footer">
        <div className="result-meta mono">
          <span className="source-label">Source {result.source}</span>
          {mode === "search" ? (
            <span className="confidence-score">
              Score {Number(result.confidence_score || 0).toFixed(3)}
            </span>
          ) : null}
        </div>

        <button type="button" className="button-secondary mono" onClick={onViewFullPrompt}>
          View Full Prompt
        </button>
      </div>
    </article>
  )
}
