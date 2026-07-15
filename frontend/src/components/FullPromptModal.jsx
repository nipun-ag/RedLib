export function FullPromptModal({ isOpen, loading, error, prompt, onClose }) {
  if (!isOpen) {
    return null
  }

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="full-prompt-title">
      <div className="modal-panel">
        <div className="modal-header">
          <div>
            <div className="eyebrow mono">Prompt Inspection</div>
            <h2 id="full-prompt-title" className="result-technique">
              {loading ? "Loading Full Prompt" : prompt?.technique || "Full Prompt"}
            </h2>
            {prompt ? (
              <div className="modal-meta mono">
                <span>Prompt ID {prompt.id}</span>
                <span>Source {prompt.source}</span>
              </div>
            ) : null}
          </div>

          <button type="button" className="button-secondary mono" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="modal-body">
          {error ? <div className="status-note">{error}</div> : null}
          {loading ? <div className="loading-line mono">Fetching full prompt body</div> : null}
          {!loading && !error && prompt ? (
            <pre className="prompt-panel">{prompt.full_prompt}</pre>
          ) : null}
        </div>

        <div className="footer-note mono">Plain-text prompt view.</div>
      </div>
    </div>
  )
}
