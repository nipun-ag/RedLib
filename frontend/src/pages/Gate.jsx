import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL, GATE_STORAGE_KEY } from "../config";
import { formatNumber } from "../lib/utils";

export default function Gate() {
  const navigate = useNavigate();
  const [acknowledged, setAcknowledged] = useState(false);
  const [totalPrompts, setTotalPrompts] = useState(null);

  useEffect(() => {
    const existing = window.localStorage.getItem(GATE_STORAGE_KEY);
    if (existing === "true") {
      navigate("/workspace", { replace: true });
      return;
    }

    let isActive = true;

    async function loadStats() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        if (!response.ok) {
          return;
        }

        const data = await response.json();
        if (isActive) {
          setTotalPrompts(data.total_prompts ?? null);
        }
      } catch {
        // The gate keeps a graceful fallback if stats are unavailable.
      }
    }

    loadStats();

    return () => {
      isActive = false;
    };
  }, [navigate]);

  function handleEnter() {
    if (!acknowledged) {
      return;
    }

    window.localStorage.setItem(GATE_STORAGE_KEY, "true");
    navigate("/workspace");
  }

  return (
    <main className="gate-shell">
      <section className="gate-card">
        <div className="gate-eyebrow">Red team corpus access</div>
        <h1 className="gate-title">Real jailbreak prompts. For research.</h1>

        <div className="gate-stat">
          <span className="gate-stat-number">{totalPrompts ? formatNumber(totalPrompts) : "--"}</span>
          <span className="gate-stat-label">curated corpus records available for study</span>
        </div>

        <div className="gate-conditions" aria-label="Access conditions">
          <p>Use this corpus to understand adversarial prompting patterns, not to operationalize them.</p>
          <p>Inspect prompts only inside controlled research, safety, or evaluation workflows.</p>
          <p>Do not reproduce, redistribute, or repurpose full prompts outside approved research contexts.</p>
        </div>

        <label className="gate-checkbox-row">
          <input
            className="gate-checkbox"
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          <span>I understand these conditions and I am entering for legitimate research use.</span>
        </label>

        <button
          className="gate-button"
          type="button"
          onClick={handleEnter}
          disabled={!acknowledged}
        >
          Enter Research Workspace
        </button>
      </section>
    </main>
  );
}
