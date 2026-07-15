export function QueryWorkbench({
  mode,
  searchDraft,
  resultCount,
  activeCategory,
  isBusy,
  onModeChange,
  onSearchDraftChange,
  onSearchSubmit,
  onBrowseRefresh,
}) {
  const isSearch = mode === "search"

  return (
    <>
      <section className="mode-bar">
        <div className="mode-switch" role="tablist" aria-label="mode switch">
          <button
            type="button"
            className={`mode-button mono${isSearch ? " is-active" : ""}`}
            onClick={() => onModeChange("search")}
          >
            Search Mode
          </button>
          <button
            type="button"
            className={`mode-button mono${!isSearch ? " is-active" : ""}`}
            onClick={() => onModeChange("browse")}
          >
            Browse Mode
          </button>
        </div>

        <div className="mode-meta mono">
          {isSearch
            ? `${resultCount || 0} results`
            : activeCategory
              ? `${resultCount || 0} in category`
              : "choose a category"}
        </div>
      </section>

      <section className="query-bar">
        {isSearch ? (
          <div className="query-stack">
            <div className="search-form">
              <input
                type="text"
                className="search-input"
                value={searchDraft}
                placeholder="Search a mechanism, framing pattern, or scenario"
                onChange={(event) => onSearchDraftChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    onSearchSubmit()
                  }
                }}
              />
              <button
                type="button"
                className="button-primary mono"
                disabled={isBusy}
                onClick={onSearchSubmit}
              >
                {isBusy ? "Searching..." : "Run Search"}
              </button>
            </div>
            <div className="query-subline">
              <span className="signal-chip mono">
                {activeCategory ? `Filter ${activeCategory}` : "All Techniques"}
              </span>
            </div>
          </div>
        ) : (
          <div className="query-stack">
            <div className="browse-controls">
              <button
                type="button"
                className="button-secondary mono"
                disabled={!activeCategory || isBusy}
                onClick={onBrowseRefresh}
              >
                {isBusy ? "Refreshing..." : "Refresh Category"}
              </button>
              <span className="signal-chip mono">
                {activeCategory ? `Category ${activeCategory}` : "Pick a Category"}
              </span>
            </div>
          </div>
        )}
      </section>
    </>
  )
}
