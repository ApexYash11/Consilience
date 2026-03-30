import { useState, useEffect, useCallback, useRef } from "react";

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

  // Problem 5: Frontend Race Conditions - Track AbortController for list fetch
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const fetchTasks = useCallback(async () => {
    // Skip on server-side rendering
    if (typeof window === "undefined") {
      return;
    }

    // Problem 5: Cancel previous request if one is in flight
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create a new AbortController for this fetch
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

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
          signal, // Problem 5: Pass abort signal to fetch
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch research tasks: ${response.statusText}`);
      }

      const result = await response.json();
      if (isMountedRef.current) {
        setData(result);
      }
    } catch (err) {
      // Problem 5: Don't set error if request was aborted (expected behavior)
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }

      if (isMountedRef.current) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [page, pageSize]);

  // Helper: Fetch with proper URL encoding
  const fetchWithAuth = useCallback(async (url: string, init?: RequestInit): Promise<Response> => {
    const token = localStorage.getItem("consilience_access_token");
    if (!token) {
      throw new Error("No authentication token found");
    }
    return fetch(url, {
      ...init,
      headers: {
        ...init?.headers,
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
  }, []);

  // Problem 5: Task cancellation/deletion with timeout and AbortController
  const cancelTask = useCallback(async (taskId: string, timeoutMs: number = 10000): Promise<void> => {
    try {
      // Create AbortController with timeout for the cancel request
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => abortController.abort(), timeoutMs);

      try {
        const encodedTaskId = encodeURIComponent(taskId);
        const response = await fetchWithAuth(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/research/${encodedTaskId}/cancel`,
          {
            method: "POST",
            signal: abortController.signal,
          }
        );

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`Failed to cancel task: ${response.statusText}`);
        }

        // Refresh the task list after cancellation
        await fetchTasks();
      } catch (err) {
        clearTimeout(timeoutId);
        throw err;
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new Error("Cancel request timed out");
      }
      throw err;
    }
  }, [fetchWithAuth, fetchTasks]);

  // Problem 5: Task deletion with timeout and AbortController
  const deleteTask = useCallback(async (taskId: string, timeoutMs: number = 10000): Promise<void> => {
    // Create AbortController with timeout for the delete request
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), timeoutMs);

    try {
      const encodedTaskId = encodeURIComponent(taskId);
      const response = await fetchWithAuth(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/research/${encodedTaskId}`,
        {
          method: "DELETE",
          signal: abortController.signal,
        }
      );

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Failed to delete task: ${response.statusText}`);
      }

      // Refresh the task list after deletion
      await fetchTasks();
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof Error && err.name === 'AbortError') {
        throw new Error("Delete request timed out");
      }
      throw err;
    }
  }, [fetchWithAuth, fetchTasks]);

  useEffect(() => {
    isMountedRef.current = true;
    fetchTasks();

    return () => {
      isMountedRef.current = false;
      // Problem 5: Abort in-flight requests on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchTasks]);

  return { data, loading, error, refetch: fetchTasks, cancelTask, deleteTask };
}
