"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { ResearchStatus } from "@/types/research";

// PHASE 5: Adaptive polling configuration
const POLL_BASE_MS = parseInt(process.env.NEXT_PUBLIC_RESEARCH_POLL_BASE_MS || "2000");
const POLL_MAX_BACKOFF_MS = parseInt(process.env.NEXT_PUBLIC_RESEARCH_POLL_MAX_BACKOFF_MS || "15000");
const POLL_JITTER_MS = parseInt(process.env.NEXT_PUBLIC_RESEARCH_POLL_JITTER_MS || "400");

// Format remaining seconds into human-readable time format
function formatRemainingTime(seconds: number | string | null | undefined): string | undefined {
  if (!seconds) return undefined;
  
  const numSeconds = typeof seconds === 'string' ? Number(seconds) : seconds;
  if (!numSeconds || numSeconds <= 0 || isNaN(numSeconds)) return undefined;
  
  const minutes = Math.floor(numSeconds / 60);
  const secs = Math.floor(numSeconds % 60);
  
  if (minutes > 0 && secs > 0) {
    return `${minutes}m ${secs}s`;
  }
  if (minutes > 0) {
    return `${minutes}m`;
  }
  if (secs > 0) {
    return `${secs}s`;
  }
  return undefined;
}

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

  // PHASE 5: Adaptive polling state
  const [pollInterval, setPollInterval] = useState(POLL_BASE_MS);
  const [consecutiveErrors, setConsecutiveErrors] = useState(0);
  const pollIntervalRef = useRef(pollInterval);

  // Track previous progress to ensure it never goes backward
  const previousProgressRef = useRef<number>(0);

  // Track if fetch is in progress to prevent overlapping requests
  const isFetchingRef = useRef<boolean>(false);

  // Track if component is still mounted
  const isMountedRef = useRef<boolean>(true);

  // Poll timeout ID for cleanup
  const timeoutIdRef = useRef<NodeJS.Timeout | null>(null);

  // Problem 5: Frontend Race Conditions - Add AbortController for cancellable requests
  const abortControllerRef = useRef<AbortController | null>(null);

  // PHASE 5: Helper to calculate next poll interval with jitter
  const getNextPollInterval = useCallback(() => {
    const jitter = Math.random() * POLL_JITTER_MS - POLL_JITTER_MS / 2;
    return pollIntervalRef.current + jitter;
  }, []);

  const fetchStatus = useCallback(async (): Promise<ResearchStatus | null> => {
    if (!taskId) {
      setIsLoading(false);
      return null;
    }

    // Problem 5: Cancel previous request if one is in flight
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create a new AbortController for this fetch
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

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

      const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${apiUrl}/api/research/standard/${taskId}/status`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          signal,
        }
      );

      if (!response.ok) {
        let errorData: any = {};
        try {
          errorData = await response.json();
        } catch {
          // Response body not JSON, use status code
        }

        // PHASE 5: Adaptive backoff on rate limit and server errors
        if ([429, 503, 500].includes(response.status) || ['RATE_LIMIT', 'TIMEOUT', 'INTERNAL_ERROR'].includes(errorData.error_code)) {
          // Exponential backoff: 2x for 429, 1.5x for others
          const multiplier = response.status === 429 ? 2 : 1.5;
          const newInterval = Math.min(pollIntervalRef.current * multiplier, POLL_MAX_BACKOFF_MS);
          setPollInterval(newInterval);
          pollIntervalRef.current = newInterval;
          setConsecutiveErrors(c => c + 1);
        } else if (response.status === 402 || errorData.error_code === 'QUOTA_EXCEEDED') {
          // Quota exceeded - terminal error, stop polling
          if (isMountedRef.current) {
            setError(errorData.detail || "Quota exceeded");
            setIsPolling(false);
          }
          return null;
        } else if (response.status === 401) {
          if (isMountedRef.current) {
            setError("Unauthorized. Please log in again.");
          }
        } else {
          if (isMountedRef.current) {
            setError(`Failed to fetch status: ${response.statusText}`);
          }
        }

        isFetchingRef.current = false;
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

      // PHASE 5: Reset backoff on successful response
      if (consecutiveErrors > 0) {
        setConsecutiveErrors(0);
        setPollInterval(POLL_BASE_MS);
        pollIntervalRef.current = POLL_BASE_MS;
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

      return data;
    } catch (err) {
      // Don't set error if request was aborted (this is expected behavior)
      if (err instanceof Error && err.name === 'AbortError') {
        return null;
      }

      setConsecutiveErrors(c => c + 1);
      if (isMountedRef.current) {
        const message = err instanceof Error ? err.message : "Unknown error occurred";
        setError(`Failed to fetch status: ${message}`);
      }
      return null;
    } finally {
      isFetchingRef.current = false;
      setIsLoading(false);
    }
  }, [taskId, consecutiveErrors]);

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

    // PHASE 5: Set up polling with adaptive interval and jitter
    const setupNextPoll = () => {
      if (!isMountedRef.current) return;
      
      // Stop polling if task is completed or failed
      if (completedRef.current) return;

      const nextInterval = getNextPollInterval();
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
      }, Math.max(POLL_BASE_MS, nextInterval));
    };

    setupNextPoll();

    return () => {
      isMountedRef.current = false;
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
      }
      // Problem 5: Abort in-flight requests on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchStatus, getNextPollInterval]);

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
      estimatedRemaining: formatRemainingTime(status?.estimatedRemaining),
      model: status?.model,
    },
    error,
    isLoading,
    isPolling,
  };
}
