import { useMemo, useState, startTransition } from "react"
import { AppHeader } from "@/components/AppHeader"
import { CategorySidebar } from "@/components/CategorySidebar"
import { EmptyState } from "@/components/EmptyState"
import { ErrorState } from "@/components/ErrorState"
import { FullPromptModal } from "@/components/FullPromptModal"
import { ModeExplainer } from "@/components/ModeExplainer"
import { QueryWorkbench } from "@/components/QueryWorkbench"
import { ResponsibleUseGate } from "@/components/ResponsibleUseGate"
import { ResultCard } from "@/components/ResultCard"
import { SummaryPanel } from "@/components/SummaryPanel"
import { TechniqueBreakdown } from "@/components/TechniqueBreakdown"
import { useBrowse } from "@/hooks/useBrowse"
import { useCategories } from "@/hooks/useCategories"
import { usePromptDetail } from "@/hooks/usePromptDetail"
import { useResponsibleGate } from "@/hooks/useResponsibleGate"
import { useSearch } from "@/hooks/useSearch"
import { useStats } from "@/hooks/useStats"

const INITIAL_EXPLAINER = "Search returns a short grounded summary above the excerpt cards."

export function ResearchPage() {
  const { accepted, accept } = useResponsibleGate()
  const { categories, loading: categoriesLoading, error: categoriesError } = useCategories()
  const { stats, loading: statsLoading, error: statsError } = useStats()
  const search = useSearch()
  const browse = useBrowse()
  const promptModal = usePromptDetail()

  const [mode, setMode] = useState("search")
  const [activeCategory, setActiveCategory] = useState("")
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchDraft, setSearchDraft] = useState("")
  const [explainer, setExplainer] = useState(INITIAL_EXPLAINER)

  const handleModeChange = (nextMode) => {
    startTransition(() => {
      setMode(nextMode)
      if (nextMode === "browse" && activeCategory) {
        browse.loadFirstPage(activeCategory)
      }
      setExplainer(
        nextMode === "search"
          ? INITIAL_EXPLAINER
          : activeCategory
            ? `${activeCategory} is open in raw browse mode.`
            : "Browse shows raw prompt excerpts one category at a time."
      )
    })
  }

  const handleCategorySelect = (categoryName) => {
    startTransition(() => {
      setActiveCategory(categoryName)
      setExplainer(
        mode === "search"
          ? `${categoryName} is now the active search filter.`
          : `${categoryName} is open in browse mode.`
      )
      if (mode === "browse") {
        browse.loadFirstPage(categoryName)
      }
    })
  }

  const handleSearchSubmit = async () => {
    if (!searchDraft.trim()) {
      setExplainer("Enter a query to search the corpus.")
      return
    }

    setExplainer(activeCategory ? `Searching within ${activeCategory}.` : "Searching the corpus.")

    await search.runSearch(searchDraft, activeCategory || null)

    setExplainer(
      activeCategory
        ? `Showing search results for ${activeCategory}.`
        : "Showing search results from the full corpus."
    )
  }

  const visibleCategories = useMemo(
    () => categories.filter((category) => category.count > 0 || categoriesLoading),
    [categories, categoriesLoading]
  )

  const resultItems = mode === "search" ? search.data.results : browse.data.results
  const resultCount = mode === "search" ? search.data.result_count : browse.data.total
  const isBusy = mode === "search" ? search.loading : browse.loading
  const currentError = mode === "search" ? search.error : browse.error
  const showSummary = mode === "search" && search.data.answer
  const showBreakdown =
    mode === "search" && Object.keys(search.data.technique_breakdown || {}).length > 0

  if (!accepted) {
    return <ResponsibleUseGate onAccept={accept} />
  }

  return (
    <div className="shell app-shell">
      <div className="app-frame">
        <AppHeader stats={stats} loading={statsLoading} error={statsError} />

        <div className="workspace">
          <CategorySidebar
            categories={visibleCategories}
            activeCategory={activeCategory}
            loading={categoriesLoading}
            error={categoriesError}
            mode={mode}
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen((current) => !current)}
            onSelectCategory={handleCategorySelect}
          />

          <div className="content">
            <QueryWorkbench
              mode={mode}
              searchDraft={searchDraft}
              resultCount={resultCount}
              activeCategory={activeCategory}
              isBusy={isBusy}
              onModeChange={handleModeChange}
              onSearchDraftChange={setSearchDraft}
              onSearchSubmit={handleSearchSubmit}
              onBrowseRefresh={() => activeCategory && browse.loadFirstPage(activeCategory)}
            />

            <ModeExplainer message={explainer} />

            <div className="results-layout">
              <div className="results-main">
                {showSummary ? <SummaryPanel answer={search.data.answer} /> : null}

                {currentError ? (
                  <ErrorState
                    title="Request paused"
                    message={
                      currentError === "Failed to fetch"
                        ? "The API is not reachable right now. Retry when the backend is available."
                        : currentError
                    }
                  />
                ) : null}

                {!currentError && isBusy ? (
                  <EmptyState
                    title={mode === "search" ? "Searching corpus" : "Loading category"}
                    message={
                      mode === "search"
                        ? "Pulling excerpts and summary."
                        : "Pulling the next browse slice."
                    }
                    loading
                  />
                ) : null}

                {!currentError && !isBusy && resultItems.length === 0 ? (
                  <EmptyState
                    title={mode === "search" ? "No search results yet" : "Browse is ready"}
                    message={
                      mode === "search"
                        ? "Run a query to start."
                        : activeCategory
                          ? "Refresh to load this category."
                          : "Choose a category to begin."
                    }
                  />
                ) : null}

                {!currentError && !isBusy && resultItems.length > 0 ? (
                  <section className="results-list" aria-label="results">
                    {resultItems.map((result) => (
                      <ResultCard
                        key={result.id}
                        mode={mode}
                        result={result}
                        onViewFullPrompt={() => promptModal.openPrompt(result.id)}
                      />
                    ))}
                  </section>
                ) : null}

                {mode === "browse" && browse.data.next_cursor && !browse.loading ? (
                  <div className="results-panel">
                    <button
                      type="button"
                      className="button-secondary mono"
                      onClick={browse.loadNextPage}
                    >
                      Load More
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="panel-stack">
                {showBreakdown ? (
                  <TechniqueBreakdown breakdown={search.data.technique_breakdown} />
                ) : (
                  <div className="breakdown-panel">
                    <div className="eyebrow mono">Technique Mix</div>
                    <div className="panel-copy">Technique mix appears after a search.</div>
                  </div>
                )}

                <div className="breakdown-panel">
                  <div className="eyebrow mono">Session</div>
                  <div className="session-list mono">
                    <span>Mode</span>
                    <strong>{mode === "search" ? "Search" : "Browse"}</strong>
                    <span>Filter</span>
                    <strong>{activeCategory || "All"}</strong>
                    <span>Results</span>
                    <strong>{resultCount || 0}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <FullPromptModal
        isOpen={promptModal.isOpen}
        loading={promptModal.loading}
        error={promptModal.error}
        prompt={promptModal.prompt}
        onClose={promptModal.closePrompt}
      />
    </div>
  )
}
