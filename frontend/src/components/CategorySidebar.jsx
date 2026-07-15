import { CountUpValue } from "@/components/CountUpValue"

export function CategorySidebar({
  categories,
  activeCategory,
  loading,
  error,
  mode,
  sidebarOpen,
  onToggleSidebar,
  onSelectCategory,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="brand-line">
          <div className="eyebrow mono">Technique Filters</div>
          <button type="button" className="button-ghost sidebar-toggle mono" onClick={onToggleSidebar}>
            {sidebarOpen ? "Hide Filters" : "Show Filters"}
          </button>
        </div>
        <p className="sidebar-copy">
          Approved taxonomy filters stay live against the indexed corpus. Counts are fetched from the
          backend and animate in as the category rail hydrates.
        </p>
      </div>

      <div className={`sidebar-panel${sidebarOpen ? "" : " is-collapsed"}`}>
        <div className="sidebar-section">
          {error ? <div className="status-note">{error}</div> : null}

          <div className="category-list">
            {categories.map((category) => {
              const isActive = activeCategory === category.name

              return (
                <button
                  key={category.name}
                  type="button"
                  className={`category-card${isActive ? " is-active" : ""}`}
                  onClick={() => onSelectCategory(category.name)}
                >
                  <span>
                    <span className="category-icon mono">{category.icon || "taxonomy"}</span>
                    <span className="category-name">{category.name}</span>
                  </span>
                  <span className="category-count mono">
                    <CountUpValue value={category.count} loading={loading} />
                  </span>
                </button>
              )
            })}
          </div>

          <div className="sidebar-note">
            {mode === "search"
              ? "In Search Mode, the selected category constrains semantic retrieval before synthesis."
              : "In Browse Mode, selecting a category opens a deterministic raw corpus stream for that technique."}
          </div>
        </div>
      </div>
    </aside>
  )
}
