import { useEffect, useState } from "react";
import { fetchJson } from "../lib/utils";

export function useCategories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isActive = true;

    async function loadCategories() {
      setLoading(true);
      setError("");

      try {
        const data = await fetchJson("/api/categories");
        if (isActive) {
          setCategories(data.categories ?? []);
        }
      } catch (loadError) {
        if (isActive) {
          setError(loadError.message);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadCategories();

    return () => {
      isActive = false;
    };
  }, []);

  return {
    categories,
    loading,
    error,
  };
}
