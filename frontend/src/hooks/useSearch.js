import { useState } from "react";
import { fetchJson } from "../lib/utils";

export function useSearch() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runSearch(query, categoryFilter) {
    setLoading(true);
    setError("");

    try {
      const response = await fetchJson("/api/query", {
        method: "POST",
        body: JSON.stringify({
          query,
          category_filter: categoryFilter || null,
        }),
      });

      setData(response);
      return response;
    } catch (searchError) {
      setError(searchError.message);
      throw searchError;
    } finally {
      setLoading(false);
    }
  }

  function resetSearch() {
    setData(null);
    setError("");
    setLoading(false);
  }

  return {
    data,
    loading,
    error,
    runSearch,
    resetSearch,
  };
}
