"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Loader } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";

interface CostTrackerProps {
  tokens: number;
  costPerToken?: number;
  estimatedRemaining?: string;
  model?: string;
  isCompleted?: boolean;
  isFailed?: boolean;
  onCancel?: () => Promise<void>;
  isCancelling?: boolean;
}

export function CostTracker({
  tokens,
  costPerToken = 0.000006,
  estimatedRemaining,
  model,
  isCompleted = false,
  isFailed = false,
  onCancel,
  isCancelling = false,
}: CostTrackerProps) {
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const cost = useMemo(() => {
    return tokens * costPerToken;
  }, [tokens, costPerToken]);

  const handleCancelConfirm = async () => {
    if (!onCancel) return;

    setIsDeleting(true);
    try {
      await onCancel();
      setShowCancelConfirm(false);
    } catch (err) {
      console.error("Failed to cancel research:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-[var(--text-secondary)]">Cost & Usage</div>

      <div className="grid grid-cols-2 gap-3">
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            "p-3 rounded-lg border",
            "bg-[var(--bg-surface)] border-[var(--border-default)]"
          )}
        >
          <div className="text-xs text-[var(--text-tertiary)] mb-1">Tokens Used</div>
          <div className="text-lg font-semibold text-[var(--text-primary)]">
            {tokens.toLocaleString()}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className={cn(
            "p-3 rounded-lg border",
            "bg-[var(--bg-surface)] border-[var(--border-default)]"
          )}
        >
          <div className="text-xs text-[var(--text-tertiary)] mb-1">Est. Cost</div>
          <div className="text-lg font-semibold text-[var(--text-primary)]">
            ${cost.toFixed(4)}
          </div>
          <div className="text-xs text-[var(--text-tertiary)] mt-1">
            @ ${(costPerToken * 1000000).toFixed(2)}/1M tokens
          </div>
        </motion.div>
      </div>

      {estimatedRemaining && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="p-3 rounded-lg bg-[var(--bg-hover)] border border-[var(--border-default)]"
        >
          <div className="text-xs text-[var(--text-secondary)]">
            <span className="font-medium">Estimated Remaining:</span> {estimatedRemaining}
          </div>
        </motion.div>
      )}

      {model && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="p-3 rounded-lg bg-[var(--bg-hover)] border border-[var(--border-default)]"
        >
          <div className="text-xs text-[var(--text-secondary)]">
            <span className="font-medium">Model:</span> {model}
          </div>
        </motion.div>
      )}

      {!isCompleted && !isFailed && onCancel && (
        <div>
          {!showCancelConfirm ? (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Button
                onClick={() => setShowCancelConfirm(true)}
                variant="ghost"
                className="w-full text-sm"
              >
                Cancel Research
              </Button>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-2 p-3 rounded-lg bg-red-50/50 dark:bg-red-950/30 border border-red-200/50 dark:border-red-800/50"
            >
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-red-700 dark:text-red-300">
                  Are you sure? This action cannot be undone.
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={() => setShowCancelConfirm(false)}
                  variant="secondary"
                  size="sm"
                  className="flex-1"
                  disabled={isCancelling}
                >
                  Keep Research
                </Button>
                <Button
                  onClick={() => void handleCancelConfirm()}
                  variant="danger"
                  size="sm"
                  className="flex-1"
                  disabled={isCancelling}
                >
                  {isCancelling && <Loader className="h-3 w-3 mr-1 animate-spin" />}
                  Confirm Cancel
                </Button>
              </div>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}
