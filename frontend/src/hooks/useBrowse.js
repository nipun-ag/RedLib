import { useState } from "react";
import { fetchJson } from "../lib/utils";

const PAGE_SIZE = 20;

export function useBrowse() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  async function runBrowse(category) {
    setLoading(true);
    setError("");

    try {
      const response = await fetchJson(
        `/api/browse?category=${encodeURIComponent(category)}&limit=${PAGE_SIZE}`,
      );
      setData(response);
      return response;
    } catch (browseError) {
      setError(browseError.message);
      throw browseError;
    } finally {
      setLoading(false);
    }
  }

  async function loadMore() {
    if (!data?.next_cursor || !data?.category) {
      return null;
    }

    setLoadingMore(true);
    setError("");

    try {
      const response = await fetchJson(
        `/api/browse?category=${encodeURIComponent(data.category)}&limit=${PAGE_SIZE}&cursor=${encodeURIComponent(data.next_cursor)}`,
      );

      setData((current) => ({
        ...response,
        results: [...(current?.results ?? []), ...(response.results ?? [])],
      }));

      return response;
    } catch (browseError) {
      setError(browseError.message);
      throw browseError;
    } finally {
      setLoadingMore(false);
    }
  }

  function resetBrowse() {
    setData(null);
    setError("");
    setLoading(false);
    setLoadingMore(false);
  }

  return {
    data,
    loading,
    loadingMore,
    error,
    runBrowse,
    loadMore,
    resetBrowse,
  };
}
