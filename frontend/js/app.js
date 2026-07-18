import { API_BASE_URL } from "./config.js";

const STORAGE_KEY = "redlib.researchGateAcknowledged";
const SEARCH_EXPLAINER_IDLE =
  "Enter a word, phrase, or concept and RedLib will find the most relevant prompts using vector search across 168,115 classified records.";
const SEARCH_EXPLAINER_ACTIVE =
  "Vector search across 168,115 classified records.";
const CATEGORY_COUNTS = {
  "Role-Based Task Framing": 30876,
  "Fictional / Hypothetical Framing": 55707,
  "Authority or Legitimacy Spoofing": 4788,
  "Obfuscation / Encoding": 2225,
  "Simulation or Sandbox Framing": 34585,
  "Dual-Response or Comparative Framing": 2574,
  "Legitimate Context or Research Framing": 23310,
  "Contextual Reframing or Euphemism": 14050,
};
const CATEGORY_NAMES = [
  "Role-Based Task Framing",
  "Fictional / Hypothetical Framing",
  "Authority or Legitimacy Spoofing",
  "Obfuscation / Encoding",
  "Simulation or Sandbox Framing",
  "Dual-Response or Comparative Framing",
  "Legitimate Context or Research Framing",
  "Contextual Reframing or Euphemism",
];
const CATEGORY_DESCRIPTIONS = {
  "Role-Based Task Framing":
    "Prompts that instruct the model to adopt a specific persona, professional role, or fictional identity in order to bypass its default safety constraints.",
  "Fictional / Hypothetical Framing":
    "Prompts that embed harmful requests inside fictional scenarios, thought experiments, or hypothetical situations to make the model treat them as safe to answer.",
  "Authority or Legitimacy Spoofing":
    "Prompts that impersonate authoritative figures, institutions, or system-level instructions to convince the model it is operating under special permissions.",
  "Obfuscation / Encoding":
    "Prompts that disguise their true intent through encoding schemes, wordplay, structural manipulation, or indirect language to evade safety filters.",
  "Simulation or Sandbox Framing":
    "Prompts that convince the model it is operating inside a simulation, test environment, or sandboxed context where its normal safety rules do not apply.",
  "Dual-Response or Comparative Framing":
    "Prompts that ask the model to produce two contrasting responses simultaneously, typically one safe and one unrestricted, exploiting the comparative format to extract harmful content.",
  "Legitimate Context or Research Framing":
    "Prompts that justify harmful requests by presenting them as necessary for academic research, journalism, security testing, or other socially sanctioned purposes.",
  "Contextual Reframing or Euphemism":
    "Prompts that reframe harmful requests using softer language, euphemisms, or shifted context to make the model treat dangerous content as acceptable.",
};

if (window.localStorage.getItem(STORAGE_KEY) !== "true") {
  window.location.replace("./index.html");
}

const state = {
  mode: "search",
  query: "",
  activeCategory: "",
  categories: CATEGORY_NAMES.map((name) => ({ name, count: CATEGORY_COUNTS[name] })),
  categoriesAnimated: false,
  stats: null,
  searchResults: [],
  searchSummary: "",
  hasSearched: false,
  browseResults: [],
  browseTotal: 0,
  browseLoaded: false,
  browseLoading: false,
  browseCursor: null,
  modalOpen: false,
};

const elements = {
  stats: {
    prompts: document.getElementById("stat-total-prompts"),
    sources: document.getElementById("stat-total-sources"),
  },
  sidebar: document.querySelector(".workspace-sidebar"),
  techniqueList: document.getElementById("technique-list"),
  clearFilterButton: document.getElementById("clear-filter-button"),
  modeSearchButton: document.getElementById("mode-search"),
  modeBrowseButton: document.getElementById("mode-browse"),
  searchRow: document.getElementById("search-row"),
  searchInput: document.getElementById("search-input"),
  searchButton: document.getElementById("search-button"),
  modeExplainer: document.getElementById("mode-explainer"),
  techniqueDescriptionPanel: document.getElementById("technique-description-panel"),
  techniqueDescriptionLabel: document.getElementById("technique-description-label"),
  techniqueDescriptionCopy: document.getElementById("technique-description-copy"),
  resultsArea: document.getElementById("results-area"),
  modal: document.getElementById("prompt-modal"),
  modalBackdrop: document.querySelector(".modal-backdrop"),
  modalCloseButton: document.getElementById("modal-close-button"),
  modalTechniqueTag: document.getElementById("modal-technique-tag"),
  modalPromptId: document.getElementById("modal-prompt-id"),
  modalBody: document.getElementById("modal-body"),
  modalFooter: document.getElementById("modal-footer"),
};

function formatNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US").format(value);
}

async function fetchJson(path, options = {}) {
  // Avoid attaching Content-Type on bodyless GETs so browsers can skip CORS preflight.
  const { headers: optionHeaders, ...restOptions } = options;
  const headers = { ...(optionHeaders || {}) };
  if (restOptions.body !== undefined) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...restOptions,
    headers,
  });

  if (!response.ok) {
    let message = "Request failed";

    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep fallback error copy.
    }

    throw new Error(message);
  }

  return response.json();
}

function animateNumber(element, targetValue, duration = 1000) {
  const startTime = performance.now();
  const safeTarget = typeof targetValue === "number" && targetValue >= 0 ? targetValue : 0;

  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - (1 - progress) ** 3;
    element.textContent = formatNumber(Math.round(safeTarget * eased));

    if (progress < 1) {
      window.requestAnimationFrame(tick);
    }
  }

  element.textContent = "0";
  window.requestAnimationFrame(tick);
}

function setStatLoadingState() {
  Object.values(elements.stats).forEach((node) => {
    node.textContent = "—";
    node.classList.add("skeleton-text");
  });
}

function renderStats(stats) {
  elements.stats.prompts.classList.remove("skeleton-text");
  elements.stats.sources.classList.remove("skeleton-text");

  if (!stats) {
    elements.stats.prompts.textContent = "—";
    elements.stats.sources.textContent = "—";
    return;
  }

  animateNumber(elements.stats.prompts, stats.total_prompts);
  elements.stats.sources.textContent = formatNumber(stats.total_sources);
}

async function loadStats() {
  setStatLoadingState();

  try {
    const data = await fetchJson("/api/stats");
    state.stats = data;
    renderStats(data);
  } catch {
    state.stats = null;
    renderStats(null);
  }
}

function renderCategories() {
  elements.techniqueList.textContent = "";

  state.categories.forEach((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "technique-button technique-item";
    if (category.name === state.activeCategory) {
      button.classList.add("is-active");
    }

    const name = document.createElement("span");
    name.className = "technique-name";
    name.textContent = category.name;

    const count = document.createElement("span");
    count.className = "technique-count";

    if (category.count === null) {
      count.textContent = "—";
      count.classList.add("skeleton-badge");
    } else {
      count.textContent = state.categoriesAnimated ? formatNumber(category.count) : "0";
    }

    button.append(name, count);
    button.addEventListener("click", () => {
      handleCategorySelection(category.name);
    });

    elements.techniqueList.appendChild(button);
  });
}

function loadCategories() {
  renderCategories();
  window.setTimeout(() => {
    Array.from(elements.techniqueList.querySelectorAll(".technique-button")).forEach((button, index) => {
      const countNode = button.querySelector(".technique-count");
      const category = state.categories[index];

      if (countNode && category && typeof category.count === "number") {
        animateNumber(countNode, category.count, 1000);
      }
    });

    state.categoriesAnimated = true;
  }, 0);
}

function updateModeButtons() {
  const searchActive = state.mode === "search";
  elements.modeSearchButton.classList.toggle("is-active", searchActive);
  elements.modeSearchButton.setAttribute("aria-selected", String(searchActive));
  elements.modeBrowseButton.classList.toggle("is-active", !searchActive);
  elements.modeBrowseButton.setAttribute("aria-selected", String(!searchActive));
}

function updateExplainer() {
  if (state.mode === "search") {
    elements.modeExplainer.textContent = state.hasSearched
      ? SEARCH_EXPLAINER_ACTIVE
      : SEARCH_EXPLAINER_IDLE;
    return;
  }

  if (!state.activeCategory) {
    elements.modeExplainer.textContent =
      "Select a technique category from the sidebar to scroll through raw corpus records.";
    return;
  }

  if (state.browseLoading || !state.browseLoaded) {
    elements.modeExplainer.textContent = `Browsing ${state.activeCategory}...`;
    return;
  }

  const count = typeof state.browseTotal === "number" ? formatNumber(state.browseTotal) : "—";
  elements.modeExplainer.textContent = `Browsing ${count} records classified as ${state.activeCategory}.`;
}

function createStatusMessage(text, isError = false) {
  const node = document.createElement("div");
  node.className = "glass-panel status-message";
  if (isError) {
    node.classList.add("is-error");
  }
  node.textContent = text;
  return node;
}

function createSkeletonCard() {
  const card = document.createElement("div");
  card.className = "glass-panel result-card skeleton-card";
  return card;
}

function createTechniqueTag(text) {
  const tag = document.createElement("span");
  tag.className = "technique-tag";
  tag.textContent = text;
  return tag;
}

function createResultCard(result) {
  const card = document.createElement("article");
  card.className = "glass-panel result-card";

  const meta = document.createElement("div");
  meta.className = "result-meta";

  const left = document.createElement("div");
  left.className = "result-meta-left";
  left.appendChild(createTechniqueTag(result.technique || "Unknown"));

  const source = document.createElement("div");
  source.className = "result-source";
  source.textContent = result.source || "Unknown source";

  meta.append(left, source);

  const excerpt = document.createElement("p");
  excerpt.className = "result-excerpt";
  excerpt.textContent = result.prompt_excerpt || "";

  const action = document.createElement("button");
  action.type = "button";
  action.className = "prompt-link";
  action.textContent = "View Full Prompt \u2192";
  action.addEventListener("click", () => openPromptModal(result));

  card.append(meta, excerpt, action);
  return card;
}

function renderResultsLoading(includeSummarySkeleton = false) {
  elements.resultsArea.textContent = "";

  if (includeSummarySkeleton) {
    elements.resultsArea.appendChild(createSkeletonCard());
  }

  elements.resultsArea.append(createSkeletonCard(), createSkeletonCard());
}

function renderSearchResults() {
  elements.resultsArea.textContent = "";
  if (!state.hasSearched) {
    return;
  }

  const summary = document.createElement("section");
  summary.className = "glass-panel summary-card";

  const summaryTitle = document.createElement("h2");
  summaryTitle.className = "summary-title";
  summaryTitle.textContent = "AI Summary";

  const summaryCopy = document.createElement("p");
  summaryCopy.className = "summary-copy";
  summaryCopy.textContent = state.searchSummary || "No grounded summary returned.";

  summary.append(summaryTitle, summaryCopy);
  elements.resultsArea.appendChild(summary);

  state.searchResults.forEach((result) => {
    elements.resultsArea.appendChild(createResultCard(result));
  });
}

function renderBrowseResults() {
  elements.resultsArea.textContent = "";
  if (!state.activeCategory || state.browseResults.length === 0) {
    return;
  }

  state.browseResults.forEach((result) => {
    elements.resultsArea.appendChild(createResultCard(result));
  });

  if (state.browseCursor) {
    const row = document.createElement("div");
    row.className = "load-more-row";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button";
    button.textContent = "Load more";
    button.addEventListener("click", () => loadMoreBrowseResults(button));

    row.appendChild(button);
    elements.resultsArea.appendChild(row);
  }
}

function renderTechniqueDescription() {
  if (!state.activeCategory || !CATEGORY_DESCRIPTIONS[state.activeCategory]) {
    elements.techniqueDescriptionPanel.classList.add("is-hidden");
    elements.techniqueDescriptionLabel.textContent = "";
    elements.techniqueDescriptionCopy.textContent = "";
    return;
  }

  elements.techniqueDescriptionLabel.textContent = state.activeCategory;
  elements.techniqueDescriptionCopy.textContent = CATEGORY_DESCRIPTIONS[state.activeCategory];
  elements.techniqueDescriptionPanel.classList.remove("is-hidden");
}

function renderMode() {
  updateModeButtons();
  updateExplainer();
  renderTechniqueDescription();
  elements.searchRow.classList.toggle("is-hidden", state.mode === "browse");
  if (state.mode === "search") {
    renderSearchResults();
  } else {
    renderBrowseResults();
  }
}

function setMode(mode) {
  state.mode = mode;
  renderMode();
}

function triggerBrowseAttention() {
  const items = elements.sidebar.querySelectorAll(".technique-item");
  items.forEach((item) => {
    item.classList.remove("technique-pulse-active");
  });
  void elements.sidebar.offsetWidth;

  items.forEach((item) => {
    item.classList.add("technique-pulse-active");
  });

  window.setTimeout(() => {
    items.forEach((item) => {
      item.classList.remove("technique-pulse-active");
    });
  }, 1800);
}

function clearBrowseAttention() {
  elements.sidebar.querySelectorAll(".technique-item").forEach((item) => {
    item.classList.remove("technique-pulse-active");
  });
}

async function runSearch() {
  const query = elements.searchInput.value.trim();
  if (!query) {
    return;
  }

  state.query = query;
  state.mode = "search";
  state.hasSearched = false;
  updateModeButtons();
  updateExplainer();
  renderResultsLoading(true);

  try {
    const data = await fetchJson("/api/query", {
      method: "POST",
      body: JSON.stringify({
        query,
        category_filter: state.activeCategory || null,
      }),
    });

    state.searchSummary = data.answer || "";
    state.searchResults = data.results || [];
    state.hasSearched = true;
    renderMode();
  } catch (error) {
    elements.resultsArea.textContent = "";
    elements.resultsArea.appendChild(createStatusMessage(error.message, true));
  }
}

async function runBrowse(categoryName, cursor = null, append = false) {
  state.mode = "browse";
  if (!append) {
    state.browseLoading = true;
    state.browseLoaded = false;
  }
  updateModeButtons();
  updateExplainer();

  if (!append) {
    renderResultsLoading(false);
  }

  const query = new URLSearchParams({
    category: categoryName,
    limit: "20",
  });

  if (cursor) {
    query.set("cursor", cursor);
  }

  try {
    const data = await fetchJson(`/api/browse?${query.toString()}`);
    state.browseTotal = data.total;
    state.browseCursor = data.next_cursor || null;
    state.browseLoading = false;
    state.browseLoaded = true;
    state.browseResults = append
      ? [...state.browseResults, ...(data.results || [])]
      : (data.results || []);
    renderMode();
  } catch (error) {
    state.browseLoading = false;
    updateExplainer();
    elements.resultsArea.textContent = "";
    elements.resultsArea.appendChild(createStatusMessage(error.message, true));
  }
}

async function loadMoreBrowseResults(button) {
  if (!state.activeCategory || !state.browseCursor) {
    return;
  }

  button.disabled = true;
  button.textContent = "Loading...";
  await runBrowse(state.activeCategory, state.browseCursor, true);
}

async function handleCategorySelection(categoryName) {
  clearBrowseAttention();
  state.activeCategory = categoryName;
  renderCategories();
  renderMode();

  if (elements.searchInput.value.trim()) {
    await runSearch();
    return;
  }

  state.mode = "browse";
  state.browseLoading = true;
  state.browseLoaded = false;
  state.browseTotal = 0;
  state.browseResults = [];
  state.browseCursor = null;
  state.searchSummary = "";
  state.searchResults = [];
  state.hasSearched = false;
  renderMode();
  renderResultsLoading(false);
  await runBrowse(categoryName);
}

function clearFilter() {
  clearBrowseAttention();
  state.activeCategory = "";
  state.browseResults = [];
  state.browseCursor = null;
  state.browseTotal = 0;
  state.browseLoaded = false;
  state.browseLoading = false;
  state.searchSummary = "";
  state.searchResults = [];
  state.hasSearched = false;
  renderCategories();
  updateExplainer();
  renderMode();
}

function closePromptModal() {
  state.modalOpen = false;
  elements.modal.classList.add("hidden");
  elements.modal.setAttribute("aria-hidden", "true");
  elements.modalTechniqueTag.textContent = "";
  elements.modalPromptId.textContent = "";
  elements.modalFooter.textContent = "";
  elements.modalBody.textContent = "";
}

async function openPromptModal(result) {
  state.modalOpen = true;
  elements.modal.classList.remove("hidden");
  elements.modal.setAttribute("aria-hidden", "false");
  elements.modalTechniqueTag.textContent = result.technique || "";
  elements.modalPromptId.textContent = result.id || "";
  elements.modalFooter.textContent = `Source: ${result.source || "Unknown source"}`;
  elements.modalBody.textContent = "";

  const skeleton = document.createElement("div");
  skeleton.className = "skeleton-card";
  elements.modalBody.appendChild(skeleton);

  try {
    const data = await fetchJson(`/api/prompts/${encodeURIComponent(result.id)}`);
    elements.modalTechniqueTag.textContent = data.technique || result.technique || "";
    elements.modalPromptId.textContent = data.id || result.id || "";
    elements.modalFooter.textContent = `Source: ${data.source || result.source || "Unknown source"}`;
    elements.modalBody.textContent = "";

    const pre = document.createElement("pre");
    pre.className = "prompt-pre";
    pre.textContent = data.full_prompt || "";
    elements.modalBody.appendChild(pre);
  } catch (error) {
    elements.modalBody.textContent = "";
    elements.modalBody.appendChild(createStatusMessage(error.message, true));
  }
}

function bindEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
  });

  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSearch();
    }
  });

  elements.searchButton.addEventListener("click", () => {
    runSearch();
  });

  elements.modeSearchButton.addEventListener("click", () => {
    setMode("search");
  });

  elements.modeBrowseButton.addEventListener("click", () => {
    setMode("browse");
    if (!state.activeCategory) {
      triggerBrowseAttention();
    }
  });

  elements.clearFilterButton.addEventListener("click", () => {
    clearFilter();
  });

  elements.modalCloseButton.addEventListener("click", closePromptModal);
  elements.modalBackdrop.addEventListener("click", closePromptModal);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.modalOpen) {
      closePromptModal();
    }
  });
}

function init() {
  bindEvents();
  renderCategories();
  renderMode();
  loadStats();
  loadCategories();
}

init();
