import { useState, useEffect, useCallback } from "react";
import { getHealthStatus } from "../services/api";

/**
 * Custom hook to ping backend health status.
 */
export function useHealthCheck() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [latency, setLatency] = useState(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    const start = performance.now();
    try {
      const response = await getHealthStatus();
      const end = performance.now();
      setData(response);
      setLatency(Math.round(end - start));
    } catch (err) {
      setError(err.message || "Failed to reach backend");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  return {
    data,
    loading,
    error,
    latency,
    refetch: fetchHealth,
  };
}
