import CountUpNumber from "./CountUpNumber";
import { cn } from "../lib/utils";

export default function TechniqueFilters({
  categories,
  activeCategory,
  loading,
  onSelect,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-label">Techniques</div>

      <div className="technique-list">
        {(loading ? Array.from({ length: 8 }) : categories).map((category, index) => {
          if (loading) {
            return (
              <div className="technique-item technique-item-loading" key={`loading-${index}`}>
                <span className="skeleton-line technique-name-skeleton" />
                <span className="skeleton-line technique-badge-skeleton" />
              </div>
            );
          }

          const isActive = activeCategory === category.name;

          return (
            <button
              className={cn("technique-item", isActive && "technique-item-active")}
              key={category.name}
              type="button"
              onClick={() => onSelect(category)}
            >
              <span className="technique-name">{category.name}</span>
              <span className="technique-count">
                <CountUpNumber value={category.count} />
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
