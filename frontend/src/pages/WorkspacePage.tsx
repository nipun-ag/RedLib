import { Search } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Link, Navigate } from "react-router-dom"

import { LiquidAtmosphere } from "@/components/LiquidAtmosphere"
import { PromptModal } from "@/components/PromptModal"
import { ResultCard } from "@/components/ResultCard"
import { StatsBar } from "@/components/StatsBar"
import {
  TechniqueSidebar,
  type TechniqueCategory,
} from "@/components/TechniqueSidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  browseCategory,
  getCategories,
  getStats,
  queryCorpus,
  type PromptResult,
  type StatsResponse,
} from "@/lib/api"
import {
  categoryLabel,
  CATEGORY_DESCRIPTIONS,
  CATEGORY_FALLBACK_COUNTS,
  CATEGORY_NAMES,
  formatNumber,
  isGateAcknowledged,
} from "@/lib/taxonomy"
import { cn } from "@/lib/utils"

type Mode = "search" | "browse"

const SEARCH_EXPLAINER_IDLE =
  "Enter a word, phrase, or concept and RedLib will find the most relevant prompts using vector search across the classified corpus."
const SEARCH_EXPLAINER_ACTIVE = "Vector search across the classified corpus."

function fallbackCategories(): TechniqueCategory[] {
  return CATEGORY_NAMES.map((name) => ({
    name,
    count: CATEGORY_FALLBACK_COUNTS[name] ?? null,
  }))
}

export function WorkspacePage() {
  const [mode, setMode] = useState<Mode>("search")
  const [query, setQuery] = useState("")
  const [activeCategory, setActiveCategory] = useState("")
  const [categories, setCategories] = useState<TechniqueCategory[]>(
    fallbackCategories(),
  )
  const [categoriesLoading, setCategoriesLoading] = useState(true)
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [attention, setAttention] = useState(false)

  const [searchResults, setSearchResults] = useState<PromptResult[]>([])
  const [searchSummary, setSearchSummary] = useState("")
  const [techniqueBreakdown, setTechniqueBreakdown] = useState<
    Record<string, number>
  >({})
  const [hasSearched, setHasSearched] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const [browseResults, setBrowseResults] = useState<PromptResult[]>([])
  const [browseTotal, setBrowseTotal] = useState(0)
  const [browseCursor, setBrowseCursor] = useState<string | null>(null)
  const [browseLoading, setBrowseLoading] = useState(false)
  const [browseLoaded, setBrowseLoaded] = useState(false)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [loadMoreLoading, setLoadMoreLoading] = useState(false)

  const [modalResult, setModalResult] = useState<PromptResult | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const gateAcknowledged = isGateAcknowledged()

  useEffect(() => {
    if (!gateAcknowledged) {
      return
    }

    const controller = new AbortController()

    getStats(controller.signal)
      .then((data) => setStats(data))
      .catch(() => setStats(null))
      .finally(() => {
        if (!controller.signal.aborted) {
          setStatsLoading(false)
        }
      })

    return () => controller.abort()
  }, [gateAcknowledged])

  useEffect(() => {
    if (!gateAcknowledged) {
      return
    }

    const controller = new AbortController()

    getCategories(controller.signal)
      .then((data) => {
        if (data.categories?.length) {
          setCategories(
            data.categories.map((item) => ({
              name: item.name,
              count: item.count,
            })),
          )
        }
      })
      .catch(() => {
        setCategories(fallbackCategories())
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setCategoriesLoading(false)
        }
      })

    return () => controller.abort()
  }, [gateAcknowledged])

  const explainer = useMemo(() => {
    if (mode === "search") {
      return hasSearched ? SEARCH_EXPLAINER_ACTIVE : SEARCH_EXPLAINER_IDLE
    }

    if (!activeCategory) {
      return "Select a technique category from the sidebar to scroll through raw corpus records."
    }

    if (browseLoading || !browseLoaded) {
      return `Browsing ${categoryLabel(activeCategory)}...`
    }

    return `Browsing ${formatNumber(browseTotal)} records classified as ${categoryLabel(activeCategory)}.`
  }, [
    mode,
    hasSearched,
    activeCategory,
    browseLoading,
    browseLoaded,
    browseTotal,
  ])

  const runSearch = useCallback(async () => {
    const trimmed = query.trim()
    if (!trimmed) {
      return
    }

    const controller = new AbortController()
    setMode("search")
    setSearchLoading(true)
    setSearchError(null)
    setHasSearched(false)

    try {
      const data = await queryCorpus(
        trimmed,
        activeCategory || null,
        controller.signal,
      )
      setSearchSummary(data.answer || "")
      setSearchResults(data.results || [])
      setTechniqueBreakdown(data.technique_breakdown || {})
      setHasSearched(true)
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Search request failed"
      setSearchError(message)
      setSearchResults([])
      setSearchSummary("")
      setTechniqueBreakdown({})
    } finally {
      setSearchLoading(false)
    }
  }, [query, activeCategory])

  const runBrowse = useCallback(
    async (categoryName: string, cursor: string | null = null, append = false) => {
      setMode("browse")
      setBrowseError(null)

      if (!append) {
        setBrowseLoading(true)
        setBrowseLoaded(false)
      } else {
        setLoadMoreLoading(true)
      }

      try {
        const data = await browseCategory(categoryName, cursor, 20)
        setBrowseTotal(data.total)
        setBrowseCursor(data.next_cursor || null)
        setBrowseResults((current) =>
          append ? [...current, ...(data.results || [])] : data.results || [],
        )
        setBrowseLoaded(true)
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Browse request failed"
        setBrowseError(message)
        if (!append) {
          setBrowseResults([])
        }
      } finally {
        setBrowseLoading(false)
        setLoadMoreLoading(false)
      }
    },
    [],
  )

  async function handleCategorySelection(categoryName: string) {
    setAttention(false)
    setActiveCategory(categoryName)
    setQuery("")
    setSearchResults([])
    setSearchSummary("")
    setTechniqueBreakdown({})
    setHasSearched(false)
    setSearchError(null)
    setBrowseResults([])
    setBrowseCursor(null)
    setBrowseTotal(0)
    await runBrowse(categoryName)
  }

  function clearFilter() {
    setAttention(false)
    setActiveCategory("")
    setBrowseResults([])
    setBrowseCursor(null)
    setBrowseTotal(0)
    setBrowseLoaded(false)
    setBrowseLoading(false)
    setBrowseError(null)
    setSearchResults([])
    setSearchSummary("")
    setTechniqueBreakdown({})
    setHasSearched(false)
    setSearchError(null)
  }

  function handleModeChange(next: string) {
    const nextMode = next as Mode
    setMode(nextMode)
    if (nextMode === "browse" && !activeCategory) {
      setAttention(true)
      window.setTimeout(() => setAttention(false), 1800)
    } else {
      setAttention(false)
    }
  }

  function openPrompt(result: PromptResult) {
    setModalResult(result)
    setModalOpen(true)
  }

  const breakdownEntries = Object.entries(techniqueBreakdown)

  if (!gateAcknowledged) {
    return <Navigate to="/" replace />
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="relative min-h-screen overflow-hidden">
        <LiquidAtmosphere intensity="workspace" />

        <div className="relative z-10 grid min-h-screen gap-4 p-3 md:grid-cols-[280px_minmax(0,1fr)] md:p-4 xl:grid-cols-[300px_minmax(0,1fr)]">
          <div className="min-h-[280px] md:min-h-0 md:h-[calc(100vh-2rem)]">
            <TechniqueSidebar
              categories={categories}
              activeCategory={activeCategory}
              attention={attention}
              loading={categoriesLoading}
              onSelect={handleCategorySelection}
              onClear={clearFilter}
            />
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <header className="panel flex min-h-16 items-center justify-between px-5 py-4 sm:px-7">
              <Link
                to="/"
                className="font-display text-2xl tracking-tight text-foreground"
                onClick={(event) => {
                  // Keep researchers in the workspace; brand is identity, not back-nav.
                  event.preventDefault()
                }}
              >
                RedLib
              </Link>
              <a
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                href="https://github.com/nipun-ag/redlib"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </header>

            <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto pb-6">
              <div className="grid gap-5">
                <StatsBar stats={stats} loading={statsLoading} />

                <section className="grid gap-4">
                  <Tabs value={mode} onValueChange={handleModeChange}>
                    <TabsList className="h-11 rounded-none border border-border bg-secondary/40 p-1">
                      <TabsTrigger
                        value="search"
                        className="label-mono rounded-none px-5 data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                      >
                        Search
                      </TabsTrigger>
                      <TabsTrigger
                        value="browse"
                        className="label-mono rounded-none px-5 data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                      >
                        Browse
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>

                  {mode === "search" ? (
                    <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                      <div className="panel relative flex min-h-16 items-center px-4 focus-within:border-primary/40">
                        <Search
                          className="mr-3 size-5 shrink-0 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <label htmlFor="workspace-search" className="sr-only">
                          Search the classified corpus
                        </label>
                        <Input
                          id="workspace-search"
                          value={query}
                          onChange={(event) => setQuery(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.preventDefault()
                              void runSearch()
                            }
                          }}
                          placeholder="Analyze adversarial prompt patterns..."
                          className="h-12 border-0 bg-transparent px-0 text-base shadow-none focus-visible:ring-0"
                          autoComplete="off"
                        />
                      </div>
                      <Button
                        type="button"
                        size="lg"
                        className="h-16 rounded-none px-8"
                        onClick={() => void runSearch()}
                        disabled={searchLoading || !query.trim()}
                      >
                        {searchLoading ? "Searching…" : "Search"}
                      </Button>
                    </div>
                  ) : null}

                  <p className="text-sm text-muted-foreground">{explainer}</p>

                  {activeCategory && CATEGORY_DESCRIPTIONS[activeCategory] ? (
                    <section className="panel border-primary/25 bg-secondary/30 px-5 py-5">
                      <p className="label-mono text-muted-foreground">
                        {categoryLabel(activeCategory)}
                      </p>
                      <p className="mt-2 max-w-prose text-sm leading-relaxed text-foreground/85">
                        {CATEGORY_DESCRIPTIONS[activeCategory]}
                      </p>
                    </section>
                  ) : null}

                  <div className="grid gap-4" aria-live="polite">
                    {mode === "search" && searchLoading ? (
                      <>
                        <Skeleton className="h-36 w-full rounded-none bg-muted" />
                        <Skeleton className="h-40 w-full rounded-none bg-muted" />
                        <Skeleton className="h-40 w-full rounded-none bg-muted" />
                      </>
                    ) : null}

                    {mode === "search" && searchError ? (
                      <p className="panel px-5 py-5 text-sm text-destructive">
                        {searchError}
                      </p>
                    ) : null}

                    {mode === "search" && hasSearched && !searchLoading ? (
                      <>
                        <section className="panel relative overflow-hidden px-6 py-6">
                          <div className="absolute inset-y-0 left-0 w-px bg-primary" />
                          <h2 className="font-display text-xl text-foreground">
                            AI Summary
                          </h2>
                          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                            {searchSummary || "No grounded summary returned."}
                          </p>
                          {breakdownEntries.length > 0 ? (
                            <div className="mt-5 flex flex-wrap gap-2">
                              {breakdownEntries.map(([name, count]) => (
                                <span
                                  key={name}
                                  title={name}
                                  className="border border-border bg-secondary/50 px-2.5 py-1 font-mono text-[11px] tracking-wide text-muted-foreground"
                                >
                                  {categoryLabel(name)}: {formatNumber(count)}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </section>

                        {searchResults.length === 0 ? (
                          <p className="panel px-5 py-5 text-sm text-muted-foreground">
                            No matching prompts returned for this query.
                          </p>
                        ) : (
                          searchResults.map((result) => (
                            <ResultCard
                              key={result.id}
                              result={result}
                              onOpen={openPrompt}
                            />
                          ))
                        )}
                      </>
                    ) : null}

                    {mode === "browse" && browseLoading ? (
                      <>
                        <Skeleton className="h-40 w-full rounded-none bg-muted" />
                        <Skeleton className="h-40 w-full rounded-none bg-muted" />
                      </>
                    ) : null}

                    {mode === "browse" && browseError ? (
                      <p className="panel px-5 py-5 text-sm text-destructive">
                        {browseError}
                      </p>
                    ) : null}

                    {mode === "browse" &&
                    !browseLoading &&
                    activeCategory &&
                    browseResults.length === 0 &&
                    browseLoaded ? (
                      <p className="panel px-5 py-5 text-sm text-muted-foreground">
                        No records available for this category.
                      </p>
                    ) : null}

                    {mode === "browse" &&
                      browseResults.map((result) => (
                        <ResultCard
                          key={result.id}
                          result={result}
                          onOpen={openPrompt}
                        />
                      ))}

                    {mode === "browse" && browseCursor ? (
                      <div>
                        <Button
                          type="button"
                          variant="outline"
                          className={cn(
                            "label-mono h-12 rounded-none px-6",
                            loadMoreLoading && "opacity-70",
                          )}
                          disabled={loadMoreLoading}
                          onClick={() =>
                            void runBrowse(activeCategory, browseCursor, true)
                          }
                        >
                          {loadMoreLoading ? "Loading…" : "Load more"}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>

        <PromptModal
          result={modalResult}
          open={modalOpen}
          onOpenChange={setModalOpen}
        />
      </div>
    </TooltipProvider>
  )
}
