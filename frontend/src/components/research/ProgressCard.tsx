"use client";

import { motion } from "framer-motion";
import { CheckCircle2, AlertCircle, Clock } from "lucide-react";
import type { ResearchStep } from "@/types/research";
import { cn } from "@/lib/cn";

interface ProgressCardProps {
  progress: number;
  currentStep: ResearchStep | null;
  status?: "queued" | "processing" | "completed" | "failed";
  error?: string;
}

function getStepDisplayName(step: ResearchStep): string {
  const names: Record<ResearchStep, string> = {
    queued: "Queued",
    planning: "Planning",
    researching: "Researching",
    verifying: "Verifying",
    detecting: "Detecting Hallucinations",
    synthesizing: "Synthesizing",
    reviewing: "Reviewing",
    formatting: "Formatting",
    completed: "Completed",
    failed: "Failed",
  };
  return names[step] || "Processing";
}

export function ProgressCard({
  progress,
  currentStep,
  status,
  error,
}: ProgressCardProps) {
  const displayName = currentStep ? getStepDisplayName(currentStep) : "Starting...";
  const isCompleted = status === "completed" || progress === 100;
  const isFailed = status === "failed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "p-6 rounded-lg border",
        isFailed
          ? "border-red-300/50 bg-red-50/50 dark:bg-red-950/30"
          : isCompleted
            ? "border-green-300/50 bg-green-50/50 dark:bg-green-950/30"
            : "border-[var(--border-default)] bg-[var(--bg-surface)]"
      )}
    >
      <div className="space-y-4">
        {/* Header with icon and status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isFailed && (
              <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
            )}
            {isCompleted && (
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
            )}
            {!isFailed && !isCompleted && (
              <Clock className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-pulse" />
            )}

            <div>
              <div className="text-sm font-medium text-[var(--text-primary)]">
                {displayName}
              </div>
              {currentStep === "queued" && (
                <div className="text-xs text-[var(--text-tertiary)]">
                  Waiting to start
                </div>
              )}
            </div>
          </div>

          <div className="text-right">
            <div className="text-2xl font-bold text-[var(--text-primary)]">
              {isCompleted ? "100" : progress}%
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-2 bg-[var(--bg-hover)] rounded-full overflow-hidden">
          <motion.div
            className={cn(
              "h-full rounded-full transition-colors",
              isFailed ? "bg-red-500" : isCompleted ? "bg-green-500" : "bg-blue-500"
            )}
            initial={{ width: 0 }}
            animate={{ width: `${isCompleted ? 100 : progress}%` }}
            transition={{
              duration: 0.8,
              ease: "easeOut",
            }}
          />
        </div>

        {/* Error message */}
        {isFailed && error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="p-3 rounded bg-red-100/50 dark:bg-red-900/30 border border-red-200/50 dark:border-red-800/50"
          >
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          </motion.div>
        )}

        {/* Success message */}
        {isCompleted && !error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="p-3 rounded bg-green-100/50 dark:bg-green-900/30 border border-green-200/50 dark:border-green-800/50"
          >
            <p className="text-sm text-green-700 dark:text-green-300">
              Research completed successfully!
            </p>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
