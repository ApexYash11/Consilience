"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, AlertCircle } from "lucide-react";
import { Shell } from "@/components/layout";
import { Button, Card } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useResearchStatus } from "@/hooks/useResearchStatus";
import { ProgressCard } from "@/components/research/ProgressCard";
import { AgentPipeline } from "@/components/research/AgentPipeline";
import { LiveSourcesFeed } from "@/components/research/LiveSourcesFeed";
import { CostTracker } from "@/components/research/CostTracker";

export default function ResearchStatusPage() {
  const router = useRouter();
  const params = useParams();
  const taskId = params?.id as string | undefined;

  const { status, progress, currentStep, sources, costData, error, isLoading, isPolling } =
    useResearchStatus(taskId || null);

  // Track if we've already navigated to prevent double nav
  const hasNavigatedRef = useRef(false);
  
  // Track cancellation in-flight state
  const [isCancelling, setIsCancelling] = useState(false);

  // Handle navigation to results page after completion
  useEffect(() => {
    if (!status || hasNavigatedRef.current) return;

    if (status.status === "completed") {
      // Wait 1200ms for animations to complete
      const timer = setTimeout(() => {
        if (hasNavigatedRef.current) return;
        hasNavigatedRef.current = true;
        router.push(`/dashboard/research/${taskId}/results`);
      }, 1200);

      return () => clearTimeout(timer);
    }
  }, [status, taskId, router]);

  const handleCancel = async () => {
    if (!taskId || isCancelling) return;

    setIsCancelling(true);
    try {
      const token = localStorage.getItem("consilience_access_token");
      if (!token) throw new Error("Not authenticated");

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/research/standard/${taskId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to cancel research");
      }

      // Redirect back to research list
      router.push("/dashboard/research");
    } catch (err) {
      console.error("Failed to cancel research:", err);
      alert(`Failed to cancel research: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const isCompleted = status?.status === "completed";
  const isFailed = status?.status === "failed";

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[1200px] mx-auto space-y-6">
          {/* Header with back button */}
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3"
          >
            <Button
              onClick={() => {
                if (!isPolling) {
                  router.back();
                }
              }}
              variant="ghost"
              size="sm"
              disabled={isPolling}
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-3xl md:text-4xl font-medium">
                Research Status
              </h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Task ID: {taskId?.slice(0, 8)}...
              </p>
            </div>
          </motion.div>

          {/* Error state for failed request */}
          {error && !status && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-4 rounded-lg border border-red-300/50 bg-red-50/50 dark:bg-red-950/30"
            >
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-700 dark:text-red-300">
                    Error Loading Research Status
                  </p>
                  <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
                  <Button
                    onClick={() => router.push("/dashboard/research")}
                    variant="secondary"
                    size="sm"
                    className="mt-3"
                  >
                    Return to Research List
                  </Button>
                </div>
              </div>
            </motion.div>
          )}

          {/* Loading skeleton */}
          {isLoading && !status && (
            <div className="space-y-4">
              <Card className="p-6">
                <div className="space-y-4 animate-pulse">
                  <div className="h-8 bg-[var(--bg-hover)] rounded w-1/3" />
                  <div className="h-2 bg-[var(--bg-hover)] rounded" />
                  <div className="h-4 bg-[var(--bg-hover)] rounded w-2/3 mt-4" />
                </div>
              </Card>
            </div>
          )}

          {/* Main content when loaded */}
          {status && (
            <motion.div layout className="space-y-6">
              {/* Progress Card */}
              <ProgressCard
                progress={progress}
                currentStep={currentStep}
                status={status.status}
                error={status.error}
              />

              {/* Two-column layout */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left column - Pipeline and Sources */}
                <div className="lg:col-span-2 space-y-6">
                  {/* Agent Pipeline */}
                  <Card className="p-4">
                    <AgentPipeline
                      currentStep={currentStep}
                      isLoading={isLoading}
                    />
                  </Card>

                  {/* Live Sources Feed */}
                  <Card className="p-4">
                    <LiveSourcesFeed sources={sources} />
                  </Card>
                </div>

                {/* Right column - Cost Tracker */}
                <div>
                  <Card className="p-4 sticky top-6">
                    <CostTracker
                      tokens={costData.tokens}
                      costPerToken={0.000006}
                      estimatedRemaining={costData.estimatedRemaining}
                      model={costData.model}
                      isCompleted={isCompleted}
                      isFailed={isFailed}
                      onCancel={!isCompleted && !isFailed ? handleCancel : undefined}
                      isCancelling={isCancelling}
                    />
                  </Card>
                </div>
              </div>

              {/* Failed state action buttons */}
              {isFailed && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3 justify-center"
                >
                  <Button
                    onClick={() => router.push("/dashboard/research")}
                    variant="secondary"
                  >
                    Return to Research
                  </Button>
                  <Button
                    onClick={() => router.push("/dashboard/research/new")}
                    variant="primary"
                  >
                    Try Again
                  </Button>
                  <Button
                    onClick={() => window.location.href = "mailto:support@consilience.ai"}
                    variant="ghost"
                  >
                    Contact Support
                  </Button>
                </motion.div>
              )}
            </motion.div>
          )}
        </div>
      </Shell>
    </ProtectedRoute>
  );
}
