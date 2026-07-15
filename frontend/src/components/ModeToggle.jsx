import { cn } from "../lib/utils";

const OPTIONS = [
  { value: "search", label: "Search" },
  { value: "browse", label: "Browse" },
];

export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode-toggle" role="tablist" aria-label="Research mode">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={mode === option.value}
          className={cn("mode-toggle-button", mode === option.value && "mode-toggle-active")}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
