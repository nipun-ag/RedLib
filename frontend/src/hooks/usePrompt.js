import { useEffect, useState } from "react";
import { fetchJson } from "../lib/utils";

export function usePrompt(promptId, isOpen) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isOpen || !promptId) {
      return undefined;
    }

    let isActive = true;

    async function loadPrompt() {
      setLoading(true);
      setError("");

      try {
        const response = await fetchJson(`/api/prompts/${encodeURIComponent(promptId)}`);
        if (isActive) {
          setData(response);
        }
      } catch (promptError) {
        if (isActive) {
          setError(promptError.message);
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadPrompt();

    return () => {
      isActive = false;
    };
  }, [isOpen, promptId]);

  useEffect(() => {
    if (!isOpen) {
      setLoading(false);
      setError("");
      setData(null);
    }
  }, [isOpen]);

  return {
    data,
    loading,
    error,
  };
}
