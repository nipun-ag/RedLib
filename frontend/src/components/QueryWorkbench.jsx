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
            ? `${resultCount || 0} current semantic results`
            : activeCategory
              ? `${resultCount || 0} prompts in category`
              : "category selection required"}
        </div>
      </section>

      <section className="query-bar">
        {isSearch ? (
          <div className="query-stack">
            <div className="eyebrow mono">Semantic Search</div>
            <div className="search-form">
              <input
                type="text"
                className="search-input"
                value={searchDraft}
                placeholder="Describe a jailbreak mechanism, framing pattern, or scenario cluster"
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
              <span>AI summary stays under the excerpt cards and never renders a full prompt body.</span>
            </div>
          </div>
        ) : (
          <div className="query-stack">
            <div className="eyebrow mono">Raw Corpus Browse</div>
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
            <div className="query-subline">
              <span>Browse Mode paginates the raw corpus directly and omits the answer synthesis layer.</span>
            </div>
          </div>
        )}
      </section>
    </>
  )
}
