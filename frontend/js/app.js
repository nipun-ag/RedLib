// Global state
let activeCategory = null;
let currentQuery = "";
let activePromptRequestId = 0;
const TECHNIQUE_DEFINITIONS = [
    { name: "Persona Hijacking", icon: "psychology_alt" },
    { name: "Fictional Framing", icon: "movie" },
    { name: "Authority Impersonation", icon: "admin_panel_settings" },
    { name: "Token Manipulation", icon: "code" },
    { name: "Gradual Escalation", icon: "trending_up" },
    { name: "Hypothetical Distancing", icon: "science" },
    { name: "Instruction Injection", icon: "edit_note" },
    { name: "Social Engineering", icon: "sentiment_very_dissatisfied" },
    { name: "Multi-language Switching", icon: "translate" },
    { name: "Payload Splitting", icon: "call_split" },
];

// On page load
document.addEventListener("DOMContentLoaded", function () {
    // Check consent
    if (localStorage.getItem("redlib_consent") !== "true") {
        window.location.href = "index.html";
        return;
    }

    renderTechniqueList(
        TECHNIQUE_DEFINITIONS.map((technique) => ({
            ...technique,
            count: null,
        })),
    );

    // Load initial data
    Promise.all([loadCategories(), loadStats()]).catch((err) => {
        console.error("Error loading initial data:", err);
    });

    // Attach event listeners
    document
        .getElementById("search-input")
        .addEventListener("keypress", function (e) {
            if (e.key === "Enter") {
                handleSearch();
            }
        });

    document.getElementById("search-btn").addEventListener("click", handleSearch);

    document.getElementById("modal-close").addEventListener("click", closeModal);

    document
        .getElementById("modal-overlay")
        .addEventListener("click", function (e) {
            if (e.target === this) {
                closeModal();
            }
        });
});

// Load categories from API
function loadCategories() {
    return fetch(`${API_BASE}/api/categories`)
        .then((res) => res.json())
        .then((data) => {
            const countsByName = new Map(
                (data.categories || []).map((category) => [
                    category.name,
                    category.count,
                ]),
            );

            const visibleCategories = TECHNIQUE_DEFINITIONS
                .map((technique) => ({
                    ...technique,
                    count: countsByName.get(technique.name) ?? 0,
                }))
                .filter((technique) => technique.count > 0);

            if (
                activeCategory &&
                !visibleCategories.some(
                    (technique) => technique.name === activeCategory,
                )
            ) {
                activeCategory = null;
                if (currentQuery) {
                    runSearch(currentQuery, null);
                }
            }

            renderTechniqueList(visibleCategories);
        })
        .catch((err) => {
            console.error("Error loading categories:", err);
        });
}

// Render technique rows in sidebar
function renderTechniqueList(categories) {
    const list = document.getElementById("technique-list");
    list.innerHTML = "";

    categories.forEach((category) => {
        const row = document.createElement("div");
        row.className = "technique-row";
        row.dataset.technique = category.name;
        if (activeCategory === category.name) {
            row.classList.add("active");
        }

        row.innerHTML = `
            <span class="material-symbols-outlined">${category.icon || "psychology_alt"}</span>
            <span class="technique-name">${category.name}</span>
            <span class="technique-badge">${category.count ?? "..."}</span>
        `;

        row.addEventListener("click", function () {
            toggleTechnique(category.name, row);
        });

        list.appendChild(row);
    });
}

// Toggle technique selection
function toggleTechnique(technique, row) {
    if (activeCategory === technique) {
        activeCategory = null;
        document
            .querySelectorAll(".technique-row")
            .forEach((r) => r.classList.remove("active"));
    } else {
        activeCategory = technique;
        document
            .querySelectorAll(".technique-row")
            .forEach((r) => r.classList.remove("active"));
        row.classList.add("active");
    }

    // Re-run search if there's a query
    if (currentQuery) {
        handleSearch();
    }
}

// Load stats from API
function loadStats() {
    return fetch(`${API_BASE}/api/stats`)
        .then((res) => res.json())
        .then((data) => {
            document.getElementById("stat-prompts").textContent =
                data.total_prompts.toLocaleString();
            document.getElementById("stat-sources").textContent = data.total_sources;
            document.getElementById("stat-sync").textContent = data.last_sync;
            document.getElementById("last-sync-date").textContent = data.last_sync;
        })
        .catch((err) => {
            console.error("Error loading stats:", err);
            document.getElementById("stat-prompts").textContent = "—";
            document.getElementById("stat-sources").textContent = "—";
            document.getElementById("stat-sync").textContent = "—";
            document.getElementById("last-sync-date").textContent = "—";
        });
}

// Handle search
function handleSearch() {
    const query = document.getElementById("search-input").value.trim();
    if (!query) return;

    currentQuery = query;
    runSearch(query, activeCategory);
}

// Run search query
function runSearch(query, categoryFilter) {
    // Show loading state
    showLoadingState();

    const body = {
        query: query,
        category_filter: categoryFilter,
    };

    fetch(`${API_BASE}/api/query`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    })
        .then((res) => res.json())
        .then((data) => {
            renderResults(data);
        })
        .catch((err) => {
            console.error("Query failed:", err);
            document.getElementById("results-container").innerHTML = `
                <div class="error-card">Query failed. Make sure the backend is running at localhost:8000.</div>
            `;
            document.getElementById("ai-summary").classList.remove("visible");
        });
}

// Show loading skeleton cards
function showLoadingState() {
    document.getElementById("ai-summary").classList.remove("visible");
    document.getElementById("result-count").classList.remove("visible");
    document.getElementById("results-container").innerHTML = `
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
    `;
}

// Render search results
function renderResults(data) {
    // Show AI summary if available
    if (data.answer) {
        document.getElementById("summary-text").textContent = data.answer;
        document.getElementById("ai-summary").classList.add("visible");
    } else {
        document.getElementById("ai-summary").classList.remove("visible");
    }

    // Render result cards
    const container = document.getElementById("results-container");
    container.innerHTML = "";

    if (data.results.length === 0) {
        container.innerHTML =
            '<div class="error-card">No results found. Try a different query or technique.</div>';
        document.getElementById("result-count").classList.remove("visible");
    } else {
        data.results.forEach((result) => {
            container.appendChild(createResultCard(result));
        });

        // Show result count
        const countEl = document.getElementById("result-count");
        countEl.textContent = `Showing ${data.result_count} result${data.result_count !== 1 ? "s" : ""}`;
        countEl.classList.add("visible");
    }
}

// Create result card element
function createResultCard(result) {
    const card = document.createElement("div");
    card.className = "result-card";

    const confidenceClass =
        result.confidence === "HIGH"
            ? "high"
            : result.confidence === "MED"
              ? "med"
              : "low";

    card.innerHTML = `
        <div class="result-card-top">
            <div class="result-card-top-left">
                <span class="technique-tag">${escapeHtml(result.technique)}</span>
                <span class="confidence ${confidenceClass}">
                    <span class="confidence-dot"></span>
                    ${result.confidence}
                </span>
            </div>
            <span class="prompt-id">${escapeHtml(result.id)}</span>
        </div>
        <div class="prompt-text">${escapeHtml(result.prompt_excerpt)}</div>
        <div class="result-card-bottom">
            <span class="result-source">
                Source: <span class="result-source-name">${escapeHtml(result.source)}</span>
            </span>
            <span class="result-action-link">View Full Prompt &rarr;</span>
        </div>
    `;

    card.querySelector(".result-action-link").addEventListener("click", function (e) {
        e.stopPropagation();
        openModal(result);
    });

    return card;
}

// Open modal
function openModal(result) {
    activePromptRequestId += 1;
    const requestId = activePromptRequestId;

    document.getElementById("modal-prompt-id").textContent = `ID: ${result.id}`;

    const techniqueTag = document.createElement("span");
    techniqueTag.className = "technique-tag";
    techniqueTag.textContent = result.technique;
    document.getElementById("modal-technique").innerHTML = "";
    document.getElementById("modal-technique").appendChild(techniqueTag);

    document.getElementById("modal-source").textContent = result.source;
    setModalState("loading", "Loading full prompt...");
    document.getElementById("modal-overlay").classList.add("visible");

    fetch(`${API_BASE}/api/prompts/${encodeURIComponent(result.id)}`)
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.detail || "Failed to load full prompt.");
            }
            return data;
        })
        .then((data) => {
            if (requestId !== activePromptRequestId) return;

            document.getElementById("modal-prompt-id").textContent = `ID: ${data.id}`;
            document.getElementById("modal-source").textContent = data.source;
            setModalState("loaded", data.full_prompt);
        })
        .catch((err) => {
            if (requestId !== activePromptRequestId) return;

            console.error("Full prompt fetch failed:", err);
            setModalState(
                "error",
                err.message || "Failed to load full prompt.",
            );
        });
}

// Close modal
function closeModal() {
    activePromptRequestId += 1;
    document.getElementById("modal-overlay").classList.remove("visible");
}

function setModalState(state, text) {
    const modalText = document.getElementById("modal-prompt-text");
    modalText.classList.remove("is-loading", "is-error");

    if (state === "loading") {
        modalText.classList.add("is-loading");
    } else if (state === "error") {
        modalText.classList.add("is-error");
    }

    modalText.textContent = text;
}

// Utility: escape HTML
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
