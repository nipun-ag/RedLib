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

const INITIAL_EXPLAINER = {
  title: "Research Modes",
  body:
    "Semantic Search synthesizes retrieved prompt clusters into an analytical summary. Browse Mode skips synthesis and exposes raw corpus slices directly from the approved taxonomy.",
  meta: "Search keeps the prompt body excerpted. Full prompt text is loaded only after explicit review action.",
}

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
          : {
              title: "Direct Corpus Browsing",
              body:
                "Browse Mode uses Qdrant scroll pagination on one approved category at a time. No reranking, no synthesis, and no inferred answer layer are added.",
              meta: activeCategory
                ? `Now inspecting ${activeCategory}. Load More continues the same category cursor.`
                : "Choose a technique category to open a deterministic raw-prompt stream.",
            }
      )
    })
  }

  const handleCategorySelect = (categoryName) => {
    startTransition(() => {
      setActiveCategory(categoryName)
      setExplainer({
        title: categoryName,
        body:
          mode === "search"
            ? "The category filter constrains semantic retrieval on technique metadata before answer synthesis runs."
            : "Browse Mode is now scoped to this technique family only. Results are raw excerpts from the stored corpus.",
        meta:
          mode === "search"
            ? "Run a query to inspect how this mechanism appears across retrieved prompts."
            : "Pagination remains inside this category until you switch filters.",
      })
      if (mode === "browse") {
        browse.loadFirstPage(categoryName)
      }
    })
  }

  const handleSearchSubmit = async () => {
    if (!searchDraft.trim()) {
      setExplainer({
        title: "Search Input Needed",
        body:
          "Semantic Search expects a natural-language research query. Use a mechanism, scenario, or pattern description rather than a full prompt body.",
        meta: "Example: cross-turn role framing with authority cues",
      })
      return
    }

    setExplainer({
      title: "Semantic Retrieval In Flight",
      body:
        "RedLib is retrieving and reranking corpus-grounded prompt nodes, then synthesizing a short analytical summary from the returned set.",
      meta: activeCategory
        ? `Technique filter active: ${activeCategory}`
        : "No category filter active. Retrieval can span the full approved taxonomy.",
    })

    await search.runSearch(searchDraft, activeCategory || null)

    setExplainer({
      title: "Search Results Loaded",
      body:
        "Result cards stay excerpt-based to preserve controlled inspection. Confidence signals reflect retrieval score bands, not a model certainty claim about the prompt itself.",
      meta: activeCategory
        ? `Filtered to ${activeCategory}. Use View Full Prompt to inspect a source record on demand.`
        : "Open a full prompt only when needed. The modal fetch remains separate from search retrieval.",
    })
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

            <ModeExplainer {...explainer} />

            <div className="results-layout">
              <div className="results-main">
                {showSummary ? <SummaryPanel answer={search.data.answer} /> : null}

                {currentError ? (
                  <ErrorState title="Request Failed" message={currentError} />
                ) : null}

                {!currentError && isBusy ? (
                  <EmptyState
                    title="Loading Research View"
                    message="RedLib is resolving the current request against the corpus."
                    loading
                  />
                ) : null}

                {!currentError && !isBusy && resultItems.length === 0 ? (
                  <EmptyState
                    title={mode === "search" ? "No Search Results Yet" : "Browse Stream Empty"}
                    message={
                      mode === "search"
                        ? "Run a semantic query to generate an answer summary and excerpt-based prompt cards."
                        : activeCategory
                          ? "This category is selected, but no browse results are currently loaded."
                          : "Choose a technique category to start raw corpus browsing."
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
                    <div className="eyebrow mono">Inspection Rules</div>
                    <div className="panel-copy">
                      Search results never render full prompt text inline. Use the
                      <span className="text-accent"> View Full Prompt</span> action only when you need
                      explicit source inspection.
                    </div>
                  </div>
                )}

                <div className="breakdown-panel">
                  <div className="eyebrow mono">Current State</div>
                  <div className="panel-copy">
                    {mode === "search"
                      ? "Semantic Search returns an analytical answer, excerpt-based prompt cards, and a per-result technique mix from the retrieved set."
                      : activeCategory
                        ? `Browse Mode is paginating the ${activeCategory} category directly from the stored corpus.`
                        : "Browse Mode is idle until a technique category is selected."}
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
