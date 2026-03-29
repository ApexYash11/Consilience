"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { ResearchStatus } from "@/types/research";

const POLL_INTERVAL = 2000; // 2 seconds

interface UseResearchStatusReturn {
  status: ResearchStatus | null;
  progress: number;
  currentStep: ResearchStatus["currentStep"] | null;
  sources: ResearchStatus["sources"];
  costData: {
    tokens: number;
    cost: number;
    estimatedRemaining?: string;
    model?: string;
  };
  error: string | null;
  isLoading: boolean;
  isPolling: boolean;
}

export function useResearchStatus(taskId: string | null): UseResearchStatusReturn {
  const [status, setStatus] = useState<ResearchStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(false);

  // Track previous progress to ensure it never goes backward
  const previousProgressRef = useRef<number>(0);

  // Track if fetch is in progress to prevent overlapping requests
  const isFetchingRef = useRef<boolean>(false);

  // Track if component is still mounted
  const isMountedRef = useRef<boolean>(true);

  // Poll timeout ID for cleanup
  const timeoutIdRef = useRef<NodeJS.Timeout | null>(null);

  const fetchStatus = useCallback(async (): Promise<ResearchStatus | null> => {
    if (!taskId) {
      setIsLoading(false);
      return null;
    }

    // Prevent overlapping requests
    if (isFetchingRef.current) {
      return null;
    }

    isFetchingRef.current = true;
    setIsPolling(true);

    try {
      const token = localStorage.getItem("consilience_access_token");
      if (!token) {
        if (isMountedRef.current) {
          setError("No authentication token found");
          setIsLoading(false);
        }
        isFetchingRef.current = false;
        setIsPolling(false);
        return null;
      }

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${apiUrl}/api/research/standard/${taskId}/status`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          if (isMountedRef.current) {
            setError("Unauthorized. Please log in again.");
            // Could trigger redirect to login here
          }
        } else if (response.status === 429) {
          if (isMountedRef.current) {
            setError("Too many requests. Please slow down.");
          }
        } else if (response.status >= 500) {
          if (isMountedRef.current) {
            setError("Server error. Please try again later.");
          }
        } else {
          if (isMountedRef.current) {
            setError(`Failed to fetch status: ${response.statusText}`);
          }
        }

        isFetchingRef.current = false;
        setIsPolling(false);
        setIsLoading(false);
        return null;
      }

      const data: ResearchStatus = await response.json();

      if (!isMountedRef.current) {
        isFetchingRef.current = false;
        setIsPolling(false);
        return null;
      }

      // Validate response structure
      if (!data.id || data.progress === undefined) {
        setError("Invalid response format from server");
        isFetchingRef.current = false;
        setIsPolling(false);
        setIsLoading(false);
        return null;
      }

      // Ensure progress never goes backward
      const validProgress = Math.max(previousProgressRef.current, data.progress || 0);
      if (!isNaN(validProgress)) {
        previousProgressRef.current = validProgress;
      }

      setStatus(data);
      setError(null);

      // Stop polling when task is completed or failed
      if (data.status === "completed" || data.status === "failed") {
        setIsPolling(false);
      }

      // Return the fetched data for use in promise callbacks
      return data;
    } catch (err) {
      if (isMountedRef.current) {
        const message = err instanceof Error ? err.message : "Unknown error occurred";
        setError(`Failed to fetch status: ${message}`);
      }
      return null;
    } finally {
      isFetchingRef.current = false;
      setIsPolling(false);
      setIsLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    isMountedRef.current = true;
    const completedRef = { current: false };

    // Initial fetch
    void fetchStatus().then((data) => {
      // Check if status is terminal based on fetched data
      if (data?.status === "completed" || data?.status === "failed") {
        completedRef.current = true;
      }
    });

    // Set up polling
    const setupNextPoll = () => {
      if (!isMountedRef.current) return;
      
      // Stop polling if task is completed or failed
      if (completedRef.current) return;

      timeoutIdRef.current = setTimeout(() => {
        void fetchStatus().then((data) => {
          // Update terminal state based on returned data
          if (data?.status === "completed" || data?.status === "failed") {
            completedRef.current = true;
          }
          
          // Schedule next poll if still polling
          if (isMountedRef.current && !completedRef.current) {
            setupNextPoll();
          }
        });
      }, POLL_INTERVAL);
    };

    setupNextPoll();

    return () => {
      isMountedRef.current = false;
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
      }
    };
  }, [fetchStatus]);

  return {
    status,
    progress: Math.max(previousProgressRef.current, status?.progress || 0),
    currentStep: status?.currentStep || null,
    sources: status?.sources || [],
    costData: {
      tokens: status?.tokens || 0,
      cost: status && status.tokens && status.costPerToken
        ? status.tokens * status.costPerToken
        : 0,
      estimatedRemaining: status?.estimatedRemaining,
      model: status?.model,
    },
    error,
    isLoading,
    isPolling,
  };
}
