import { useState } from "react"

export function ResponsibleUseGate({ onAccept }) {
  const [confirmed, setConfirmed] = useState(false)
  const [showError, setShowError] = useState(false)

  const handleContinue = () => {
    if (!confirmed) {
      setShowError(true)
      return
    }

    onAccept()
  }

  return (
    <div className="gate-screen">
      <div className="gate-panel">
        <div className="gate-grid">
          <section className="gate-copy">
            <div className="eyebrow mono">Responsible Use Gate</div>
            <h1 className="headline">Real jailbreak prompts for research and defense.</h1>
            <p className="lede">
              RedLib is a research environment for trust and safety practitioners, red teamers, and
              security researchers studying real adversarial prompt behavior across a classified
              corpus.
            </p>

            <div className="gate-facts">
              <div className="gate-fact">
                <strong className="mono">168,115</strong>
                <span className="mono">curated prompt records</span>
              </div>
              <div className="gate-fact">
                <strong className="mono">8</strong>
                <span className="mono">approved technique families</span>
              </div>
              <div className="gate-fact">
                <strong className="mono">2</strong>
                <span className="mono">inspection modes</span>
              </div>
            </div>
          </section>

          <section className="gate-rules">
            <div className="eyebrow mono">Access Conditions</div>
            <ul>
              <li>Use the corpus for defensive analysis, evaluation, or safety research only.</li>
              <li>Do not treat RedLib as an execution guide or a source of operational jailbreak instructions.</li>
              <li>Search results stay excerpt-based by default. Full prompt text requires explicit inspection.</li>
              <li>Source attribution is preserved so records remain auditable and reviewable.</li>
            </ul>

            <div className="gate-ack">
              <label className="gate-checkbox">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => {
                    setConfirmed(event.target.checked)
                    if (event.target.checked) {
                      setShowError(false)
                    }
                  }}
                />
                <span>
                  I understand that RedLib is intended for responsible AI safety research and that I
                  should use this interface only for analysis, evaluation, or defensive work.
                </span>
              </label>

              <div className="action-row">
                <button type="button" className="button-primary mono" onClick={handleContinue}>
                  Enter Research Workspace
                </button>
                <div className="text-dim mono">Session acknowledgment is stored locally in this browser.</div>
              </div>
              {showError ? <div className="status-note">You must confirm the responsible-use statement before continuing.</div> : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
