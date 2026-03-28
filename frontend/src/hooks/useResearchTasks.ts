import { useState, useEffect, useCallback } from "react";

export interface ResearchTask {
  task_id: string;
  title: string;
  description: string;
  depth: "standard" | "deep";
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "paused";
  created_at: string;
  completed_at?: string;
  estimated_cost_usd?: number;
  actual_cost_usd?: number;
  progress_percent: number;
}

export interface ResearchListResponse {
  tasks: ResearchTask[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function useResearchTasks(page: number = 1, pageSize: number = 10) {
  const [data, setData] = useState<ResearchListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    // Skip on server-side rendering
    if (typeof window === "undefined") {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem("consilience_access_token");
      if (!token) {
        setError("No authentication token found");
        setLoading(false);
        return;
      }

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/research/list?${params}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch research tasks: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return { data, loading, error, refetch: fetchTasks };
}
