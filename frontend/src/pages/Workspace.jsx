import { useEffect, useMemo, useState } from "react";
import AISummaryCard from "../components/AISummaryCard";
import BrowseCard from "../components/BrowseCard";
import FullPromptModal from "../components/FullPromptModal";
import Header from "../components/Header";
import ModeExplainer from "../components/ModeExplainer";
import ModeToggle from "../components/ModeToggle";
import ResultCard from "../components/ResultCard";
import SearchInput from "../components/SearchInput";
import StatBar from "../components/StatBar";
import TechniqueFilters from "../components/TechniqueFilters";
import { useBrowse } from "../hooks/useBrowse";
import { useCategories } from "../hooks/useCategories";
import { useSearch } from "../hooks/useSearch";
import { fetchJson } from "../lib/utils";

export default function Workspace() {
  const { categories, loading: categoriesLoading } = useCategories();
  const search = useSearch();
  const browse = useBrowse();

  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");
  const [mode, setMode] = useState("search");
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [modalPrompt, setModalPrompt] = useState(null);

  useEffect(() => {
    let isActive = true;

    async function loadStats() {
      setStatsLoading(true);
      setStatsError("");

      try {
        const response = await fetchJson("/api/stats");
        if (isActive) {
          setStats(response);
        }
      } catch (loadError) {
        if (isActive) {
          setStatsError(loadError.message);
        }
      } finally {
        if (isActive) {
          setStatsLoading(false);
        }
      }
    }

    loadStats();

    return () => {
      isActive = false;
    };
  }, []);

  const activeCategoryObject = useMemo(
    () => categories.find((category) => category.name === activeCategory) ?? null,
    [activeCategory, categories],
  );

  async function handleSearch() {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      return;
    }

    setMode("search");
    browse.resetBrowse();
    await search.runSearch(trimmedQuery, activeCategory);
  }

  async function handleCategorySelect(category) {
    setActiveCategory(category.name);

    if (query.trim()) {
      setMode("search");
      browse.resetBrowse();
      await search.runSearch(query.trim(), category.name);
      return;
    }

    setMode("browse");
    search.resetSearch();
    await browse.runBrowse(category.name);
  }

  async function handleModeChange(nextMode) {
    setMode(nextMode);

    if (nextMode === "search") {
      browse.resetBrowse();
      return;
    }

    search.resetSearch();
    if (activeCategory) {
      await browse.runBrowse(activeCategory);
    }
  }

  const currentBrowseCount = browse.data?.results?.length ?? 0;
  const currentSearchCount = search.data?.result_count ?? 0;
  const browseCategoryLabel = activeCategory || "the selected category";
  const browseTotal = activeCategoryObject?.count ?? browse.data?.total ?? 0;

  const explainerText =
    mode === "search"
      ? `Search finds the most relevant prompts using AI, then summarizes what it found. ${currentSearchCount} prompts searched.`
      : `Browsing all ${browseTotal} prompts tagged as ${browseCategoryLabel}. No AI involved, just the raw corpus.`;

  const results = mode === "search" ? search.data?.results ?? [] : browse.data?.results ?? [];
  const isResultsLoading = mode === "search" ? search.loading : browse.loading;
  const resultsError = mode === "search" ? search.error : browse.error;

  return (
    <main className="workspace-shell">
      <Header />

      <div className="workspace-frame">
        <StatBar stats={stats} loading={statsLoading} error={statsError} />

        <div className="workspace-layout">
          <TechniqueFilters
            categories={categories}
            activeCategory={activeCategory}
            loading={categoriesLoading}
            onSelect={handleCategorySelect}
          />

          <section className="workspace-main">
            <ModeToggle mode={mode} onChange={handleModeChange} />
            <SearchInput
              value={query}
              onChange={setQuery}
              onSubmit={handleSearch}
              disabled={search.loading}
            />
            <ModeExplainer text={explainerText} />

            <div className="results-stack">
              {mode === "search" && search.data?.answer ? (
                <AISummaryCard answer={search.data.answer} />
              ) : null}

              {isResultsLoading ? (
                <div className="results-loading" aria-label="Loading results">
                  <div className="result-card skeleton-card" />
                  <div className="result-card skeleton-card" />
                </div>
              ) : null}

              {!isResultsLoading && resultsError ? (
                <p className="status-text status-error">{resultsError}</p>
              ) : null}

              {!isResultsLoading && !resultsError && results.length === 0 ? (
                <p className="status-text">
                  {mode === "search"
                    ? "Run a search to inspect grounded prompt excerpts."
                    : "Select a technique to browse the raw corpus."}
                </p>
              ) : null}

              {!isResultsLoading && !resultsError ? (
                <div className="results-list">
                  {results.map((result) =>
                    mode === "search" ? (
                      <ResultCard
                        key={result.id}
                        result={result}
                        onViewPrompt={(id) =>
                          setModalPrompt({
                            id,
                            technique: result.technique,
                            source: result.source,
                          })
                        }
                      />
                    ) : (
                      <BrowseCard
                        key={result.id}
                        result={result}
                        onViewPrompt={(id) =>
                          setModalPrompt({
                            id,
                            technique: result.technique,
                            source: result.source,
                          })
                        }
                      />
                    ),
                  )}
                </div>
              ) : null}

              {mode === "browse" && currentBrowseCount > 0 && browse.data?.next_cursor ? (
                <button
                  className="load-more-button"
                  type="button"
                  onClick={() => browse.loadMore()}
                  disabled={browse.loadingMore}
                >
                  {browse.loadingMore ? "Loading..." : "Load more"}
                </button>
              ) : null}
            </div>
          </section>
        </div>
      </div>

      <FullPromptModal
        promptId={modalPrompt?.id ?? ""}
        isOpen={Boolean(modalPrompt)}
        onClose={() => setModalPrompt(null)}
        fallbackTechnique={modalPrompt?.technique}
        fallbackSource={modalPrompt?.source}
      />
    </main>
  );
}
