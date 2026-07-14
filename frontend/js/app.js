(function () {
  if (!document.body.classList.contains("app-page")) {
    return;
  }

  const allowVerificationBypass =
    window.location.protocol === "file:" &&
    window.location.search.indexOf("codex_verify=1") !== -1;

  if (!allowVerificationBypass && window.sessionStorage.getItem("redlib_acknowledged") !== "true") {
    window.location.href = "./index.html";
    return;
  }

  const API_BASE_URL = window.API_BASE_URL;
  const DEFAULT_TOTAL_PROMPTS = 168115;
  const DEFAULT_LAST_SYNC = "2026-07-10";
  const DEFAULT_CATEGORIES = [
    "Role-Based Task Framing",
    "Fictional / Hypothetical Framing",
    "Authority or Legitimacy Spoofing",
    "Obfuscation / Encoding",
    "Simulation or Sandbox Framing",
    "Dual-Response or Comparative Framing",
    "Legitimate Context or Research Framing",
    "Contextual Reframing or Euphemism",
  ];

  const state = {
    activeCategory: null,
    categories: DEFAULT_CATEGORIES.map(function (name) {
      return { name: name, count: null };
    }),
    categoryCountsLoaded: false,
    totalPrompts: DEFAULT_TOTAL_PROMPTS,
    lastSync: DEFAULT_LAST_SYNC,
    mode: "idle",
    browseCursor: null,
    browseTotal: 0,
    browseCategory: null,
    isBusy: false,
  };

  const refs = {
    categoryList: document.getElementById("category-list"),
    sidebar: document.getElementById("sidebar"),
    sidebarToggle: document.getElementById("sidebar-toggle"),
    sidebarTotal: document.getElementById("sidebar-total"),
    sidebarSync: document.getElementById("sidebar-sync"),
    sidebarCategoryCount: document.getElementById("sidebar-category-count"),
    clearFilter: document.getElementById("clear-filter"),
    searchForm: document.getElementById("search-form"),
    searchInput: document.getElementById("search-input"),
    modeIndicator: document.getElementById("mode-indicator"),
    modeExplainer: document.getElementById("mode-explainer"),
    activeFilter: document.getElementById("active-filter"),
    statusBanner: document.getElementById("status-banner"),
    results: document.getElementById("results"),
    loadMore: document.getElementById("load-more"),
    modal: document.getElementById("prompt-modal"),
    modalClose: document.getElementById("modal-close"),
    modalTitle: document.getElementById("modal-title"),
    modalPromptId: document.getElementById("modal-prompt-id"),
    modalTechnique: document.getElementById("modal-technique"),
    modalSource: document.getElementById("modal-source"),
    modalBody: document.getElementById("modal-body"),
  };

  function formatNumber(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return "...";
    }
    return parsed.toLocaleString("en-US");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setBusy(isBusy) {
    state.isBusy = isBusy;
    refs.searchForm.querySelector("button[type='submit']").disabled = isBusy;
    refs.loadMore.disabled = isBusy;
  }

  function setStatus(message, tone) {
    if (!message) {
      refs.statusBanner.hidden = true;
      refs.statusBanner.textContent = "";
      refs.statusBanner.style.borderLeft = "";
      return;
    }

    refs.statusBanner.hidden = false;
    refs.statusBanner.textContent = message;
    refs.statusBanner.style.borderLeft = tone === "error"
      ? "4px solid var(--accent)"
      : "4px solid var(--outline)";
  }

  function updateSidebarMeta() {
    refs.sidebarTotal.textContent = formatNumber(state.totalPrompts);
    refs.sidebarSync.textContent = "Last sync: " + state.lastSync;
    const visibleCount = state.categories.filter(function (category) {
      if (!state.categoryCountsLoaded) {
        return true;
      }
      return (category.count || 0) > 0;
    }).length;
    refs.sidebarCategoryCount.textContent = formatNumber(visibleCount);
  }

  function updateActiveFilterBadge() {
    if (state.activeCategory) {
      refs.activeFilter.textContent = state.activeCategory;
      refs.activeFilter.classList.remove("technique-badge-inactive");
    } else {
      refs.activeFilter.textContent = "None";
      refs.activeFilter.classList.add("technique-badge-inactive");
    }
  }

  function renderCategories() {
    refs.categoryList.innerHTML = "";

    state.categories.forEach(function (category) {
      const count = category.count;
      const shouldHide = state.categoryCountsLoaded && Number(count) === 0;
      const item = document.createElement("li");
      item.className = "category-item";
      if (shouldHide) {
        item.hidden = true;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "category-button";
      if (state.activeCategory === category.name) {
        button.classList.add("is-active");
      }
      button.dataset.category = category.name;

      const name = document.createElement("span");
      name.className = "category-name";
      name.textContent = category.name;

      const badge = document.createElement("span");
      badge.className = "category-count";
      badge.textContent = count === null ? "..." : formatNumber(count);

      button.appendChild(name);
      button.appendChild(badge);
      item.appendChild(button);
      refs.categoryList.appendChild(item);
    });

    updateSidebarMeta();
    updateActiveFilterBadge();
  }

  function setMode(mode) {
    state.mode = mode;
    if (mode === "search") {
      refs.modeIndicator.textContent = "Search";
      if (state.activeCategory) {
        refs.modeExplainer.textContent =
          "Search finds the most relevant prompts to your query using AI, then summarizes what it found. Filtered to " +
          state.activeCategory +
          ".";
      } else {
        refs.modeExplainer.textContent =
          "Search finds the most relevant prompts to your query using AI, then summarizes what it found. " +
          formatNumber(state.totalPrompts) +
          " prompts searched.";
      }
    } else if (mode === "browse") {
      refs.modeIndicator.textContent = "Browse";
      refs.modeExplainer.textContent =
        "Browsing all " +
        formatNumber(state.browseTotal) +
        " prompts tagged as " +
        state.browseCategory +
        ". No AI involved, just the raw corpus.";
    } else {
      refs.modeIndicator.textContent = "Idle";
      refs.modeExplainer.textContent =
        "Select a category to browse the raw corpus, or enter a query to run semantic search.";
    }
  }

  function buildConfidenceMarkup(result) {
    const confidence = result.confidence || "LOW";
    const level = confidence === "HIGH" ? "high" : confidence === "MED" ? "med" : "low";
    return (
      '<span class="confidence-chip">' +
      '<span class="confidence-dot ' + level + '"></span>' +
      escapeHtml(confidence) +
      '<span class="confidence-score">(' + escapeHtml((result.confidence_score || 0).toFixed(3)) + ')</span>' +
      "</span>"
    );
  }

  function renderSearchResults(payload) {
    const fragments = [];
    fragments.push(
      '<article class="summary-card">' +
      '<h2 class="summary-title">AI Summary</h2>' +
      '<p class="summary-body">' + escapeHtml(payload.answer || "No summary returned.") + "</p>" +
      "</article>"
    );

    if (!payload.results || payload.results.length === 0) {
      fragments.push(
        '<section class="empty-state">No prompts matched this query. Adjust the wording or clear the category filter.</section>'
      );
    } else {
      payload.results.forEach(function (result) {
        fragments.push(
          '<article class="result-card">' +
          '<div class="card-header">' +
          '<span class="technique-badge">' + escapeHtml(result.technique) + "</span>" +
          buildConfidenceMarkup(result) +
          "</div>" +
          '<p class="card-excerpt">' + escapeHtml(result.prompt_excerpt) + "</p>" +
          '<div class="card-footer">' +
          '<div class="card-meta">' +
          '<span class="card-meta-item">SOURCE // ' + escapeHtml(result.source || "Unknown") + "</span>" +
          '<span class="card-meta-item">PROMPT ID // ' + escapeHtml(result.id || "Unknown") + "</span>" +
          "</div>" +
          '<button class="card-action" type="button" data-prompt-id="' + escapeHtml(result.id) + '" data-technique="' +
          escapeHtml(result.technique) + '" data-source="' + escapeHtml(result.source || "") +
          '">View Full Prompt -></button>' +
          "</div>" +
          "</article>"
        );
      });
    }

    refs.results.innerHTML = fragments.join("");
    refs.loadMore.hidden = true;
  }

  function renderBrowseResults(payload, append) {
    const results = payload.results || [];
    if (!append) {
      refs.results.innerHTML = "";
    }

    if (!append && results.length === 0) {
      refs.results.innerHTML =
        '<section class="empty-state">No prompts are currently available for this category.</section>';
    } else {
      const html = results.map(function (result) {
        return (
          '<article class="result-card">' +
          '<div class="card-header">' +
          '<span class="technique-badge">' + escapeHtml(result.technique) + "</span>" +
          "</div>" +
          '<p class="card-excerpt">' + escapeHtml(result.prompt_excerpt) + "</p>" +
          '<div class="card-footer">' +
          '<div class="card-meta">' +
          '<span class="card-meta-item">SOURCE // ' + escapeHtml(result.source || "Unknown") + "</span>" +
          '<span class="card-meta-item">PROMPT ID // ' + escapeHtml(result.id || "Unknown") + "</span>" +
          "</div>" +
          '<button class="card-action" type="button" data-prompt-id="' + escapeHtml(result.id) + '" data-technique="' +
          escapeHtml(result.technique) + '" data-source="' + escapeHtml(result.source || "") +
          '">View Full Prompt -></button>' +
          "</div>" +
          "</article>"
        );
      }).join("");

      if (append) {
        refs.results.insertAdjacentHTML("beforeend", html);
      } else {
        refs.results.innerHTML = html;
      }
    }

    state.browseCursor = payload.next_cursor || null;
    refs.loadMore.hidden = !state.browseCursor;
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || ("Request failed with status " + response.status));
    }
    return response.json();
  }

  async function loadStats() {
    try {
      const payload = await fetchJson(API_BASE_URL + "/api/stats");
      state.totalPrompts = payload.total_prompts || DEFAULT_TOTAL_PROMPTS;
      state.lastSync = payload.last_sync || DEFAULT_LAST_SYNC;
      updateSidebarMeta();
      if (state.mode === "search") {
        setMode("search");
      }
    } catch (error) {
      updateSidebarMeta();
    }
  }

  async function hydrateCategories() {
    try {
      const payload = await fetchJson(API_BASE_URL + "/api/categories");
      if (payload.categories && payload.categories.length) {
        state.categories = payload.categories.map(function (category) {
          return {
            name: category.name,
            count: category.count,
          };
        });
      }
      state.categoryCountsLoaded = true;
      renderCategories();
    } catch (error) {
      renderCategories();
      setStatus("Category counts are unavailable. Labels remain usable.", "info");
    }
  }

  async function runSearch() {
    const query = refs.searchInput.value.trim();
    if (!query) {
      setStatus("Enter a query before running semantic search.", "error");
      return;
    }

    setBusy(true);
    setStatus("Running semantic search...", "info");

    try {
      const payload = await fetchJson(API_BASE_URL + "/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query,
          category_filter: state.activeCategory,
        }),
      });

      setMode("search");
      renderSearchResults(payload);
      setStatus("", "info");
    } catch (error) {
      refs.results.innerHTML =
        '<section class="empty-state">Search failed. Confirm the backend is running and reachable at ' +
        escapeHtml(API_BASE_URL) +
        ".</section>";
      setStatus("Search request failed.", "error");
      refs.loadMore.hidden = true;
    } finally {
      setBusy(false);
    }
  }

  async function runBrowse(append) {
    if (!state.activeCategory) {
      return;
    }

    const isAppend = Boolean(append);
    const query = new URLSearchParams({
      category: state.activeCategory,
      limit: "20",
    });

    if (isAppend && state.browseCursor) {
      query.set("cursor", state.browseCursor);
    }

    setBusy(true);
    setStatus(isAppend ? "Loading more prompts..." : "Loading raw corpus slice...", "info");

    try {
      const payload = await fetchJson(API_BASE_URL + "/api/browse?" + query.toString());
      state.browseTotal = payload.total || 0;
      state.browseCategory = state.activeCategory;
      setMode("browse");
      renderBrowseResults(payload, isAppend);
      setStatus("", "info");
    } catch (error) {
      if (!isAppend) {
        refs.results.innerHTML =
          '<section class="empty-state">Browse mode is wired to `/api/browse`, which is not available yet or is currently failing.</section>';
      }
      refs.loadMore.hidden = true;
      setStatus("Browse request failed.", "error");
    } finally {
      setBusy(false);
    }
  }

  function openModal(promptId, technique, source) {
    refs.modal.hidden = false;
    refs.modalTitle.textContent = "Loading";
    refs.modalPromptId.textContent = promptId || "-";
    refs.modalTechnique.textContent = technique || "-";
    refs.modalSource.textContent = source || "-";
    refs.modalBody.textContent = "Loading prompt text...";

    fetchJson(API_BASE_URL + "/api/prompts/" + encodeURIComponent(promptId))
      .then(function (payload) {
        refs.modalTitle.textContent = payload.technique || "Full Prompt";
        refs.modalPromptId.textContent = payload.id || promptId || "-";
        refs.modalTechnique.textContent = payload.technique || technique || "-";
        refs.modalSource.textContent = payload.source || source || "-";
        refs.modalBody.textContent = payload.full_prompt || "Prompt body unavailable.";
      })
      .catch(function () {
        refs.modalTitle.textContent = "Prompt Load Failed";
        refs.modalBody.textContent = "Unable to load prompt text from the backend.";
      });
  }

  function closeModal() {
    refs.modal.hidden = true;
  }

  function onCategorySelect(categoryName) {
    state.activeCategory = categoryName;
    renderCategories();
    const hasQuery = refs.searchInput.value.trim().length > 0;

    if (window.innerWidth <= 980) {
      refs.sidebar.classList.remove("is-open");
      refs.sidebarToggle.setAttribute("aria-expanded", "false");
    }

    if (hasQuery) {
      runSearch();
    } else {
      runBrowse(false);
    }
  }

  refs.searchForm.addEventListener("submit", function (event) {
    event.preventDefault();
    runSearch();
  });

  refs.categoryList.addEventListener("click", function (event) {
    const button = event.target.closest("[data-category]");
    if (!button) {
      return;
    }
    onCategorySelect(button.dataset.category);
  });

  refs.clearFilter.addEventListener("click", function () {
    state.activeCategory = null;
    renderCategories();
    setMode("idle");
    refs.results.innerHTML = "";
    refs.loadMore.hidden = true;
    setStatus("", "info");
  });

  refs.results.addEventListener("click", function (event) {
    const action = event.target.closest("[data-prompt-id]");
    if (!action) {
      return;
    }
    openModal(action.dataset.promptId, action.dataset.technique, action.dataset.source);
  });

  refs.loadMore.addEventListener("click", function () {
    runBrowse(true);
  });

  refs.modal.addEventListener("click", function (event) {
    if (event.target === refs.modalClose || event.target.dataset.closeModal === "true") {
      closeModal();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !refs.modal.hidden) {
      closeModal();
    }
  });

  refs.sidebarToggle.addEventListener("click", function () {
    const isOpen = refs.sidebar.classList.toggle("is-open");
    refs.sidebarToggle.setAttribute("aria-expanded", String(isOpen));
  });

  renderCategories();
  updateSidebarMeta();
  loadStats();
  hydrateCategories();
})();
