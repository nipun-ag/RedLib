import { useEffect } from "react";
import { usePrompt } from "../hooks/usePrompt";

export default function FullPromptModal({ promptId, isOpen, onClose, fallbackTechnique, fallbackSource }) {
  const { data, loading, error } = usePrompt(promptId, isOpen);

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const technique = data?.technique ?? fallbackTechnique ?? "";
  const source = data?.source ?? fallbackSource ?? "";

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="prompt-modal-title">
        <header className="modal-header">
          <div className="modal-header-copy">
            <span className="modal-prompt-id" id="prompt-modal-title">
              {promptId}
            </span>
            {technique ? <span className="technique-tag">{technique}</span> : null}
          </div>

          <button className="modal-close" type="button" onClick={onClose} aria-label="Close full prompt">
            Close
          </button>
        </header>

        <div className="modal-body">
          {loading ? (
            <div className="modal-skeleton">
              <span className="skeleton-line modal-skeleton-line" />
              <span className="skeleton-line modal-skeleton-line" />
              <span className="skeleton-line modal-skeleton-line short" />
            </div>
          ) : error ? (
            <p className="status-text status-error">{error}</p>
          ) : (
            <pre className="prompt-body">{data?.full_prompt ?? ""}</pre>
          )}
        </div>

        <footer className="modal-footer">Source: {source || "Unknown"}</footer>
      </section>
    </div>
  );
}
