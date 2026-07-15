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
        <div className="sidebar-header">
          <div className="eyebrow mono">Technique Filters</div>
          <button
            type="button"
            className="button-ghost sidebar-toggle mono"
            onClick={onToggleSidebar}
          >
            {sidebarOpen ? "Hide Filters" : "Show Filters"}
          </button>
        </div>
        <div className="sidebar-status mono">
          {activeCategory ? activeCategory : loading ? "Loading counts" : "All techniques"}
        </div>
      </div>

      <div className={`sidebar-panel${sidebarOpen ? "" : " is-collapsed"}`}>
        <div className="sidebar-section">
          {error ? <div className="status-note">{mode === "search" ? "Counts paused" : "Filters paused"}</div> : null}

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
        </div>
      </div>
    </aside>
  )
}
