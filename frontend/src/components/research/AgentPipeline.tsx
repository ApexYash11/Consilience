"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Clock, Zap } from "lucide-react";
import type { ResearchStep, AgentState } from "@/types/research";
import { AGENTS_LIST } from "@/types/research";
import { mapStepToAgents } from "@/utils/mapStepToAgents";
import { cn } from "@/lib/cn";

const animationConfig = {
  duration: 0.4,
  ease: "easeOut",
};

interface AgentPipelineProps {
  currentStep: ResearchStep | null;
  isLoading?: boolean;
}

function getAgentIcon(state: AgentState) {
  switch (state) {
    case "done":
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "running":
      return <Zap className="h-5 w-5 text-blue-500 animate-pulse" />;
    case "waiting":
      return <Clock className="h-5 w-5 text-gray-400" />;
    default:
      return <Clock className="h-5 w-5 text-gray-400" />;
  }
}

function getAgentStateLabel(state: AgentState): string {
  switch (state) {
    case "done":
      return "Done";
    case "running":
      return "Running";
    case "waiting":
      return "Waiting";
    default:
      return "Unknown";
  }
}

export function AgentPipeline({ currentStep, isLoading = false }: AgentPipelineProps) {
  // Get agent states from the current step
  const agentStates = currentStep ? mapStepToAgents(currentStep) : {};

  // Show skeleton when loading
  if (isLoading || !currentStep) {
    return (
      <div className="space-y-3">
        <div className="text-sm font-medium text-[var(--text-secondary)]">Agent Pipeline</div>
        {AGENTS_LIST.map((agent) => (
          <div key={agent.id} className="animate-pulse">
            <div className="h-12 bg-[var(--bg-hover)] rounded-lg" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-[var(--text-secondary)]">Agent Pipeline</div>

      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {AGENTS_LIST.map((agent) => {
            const state = agentStates[agent.id] || "waiting";

            return (
              <motion.div
                key={agent.id}
                layout
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -4 }}
                transition={{ duration: animationConfig.duration }}
              >
                <div className={cn(
                  "p-3 rounded-lg border flex items-center gap-3 transition-all",
                  state === "running"
                    ? "border-blue-400/50 bg-blue-50/50 dark:bg-blue-950/30"
                    : state === "done"
                      ? "border-green-400/30 bg-green-50/30 dark:bg-green-950/20"
                      : "border-[var(--border-default)] bg-[var(--bg-surface)]"
                )}>
                  <div className="flex-shrink-0">{getAgentIcon(state)}</div>

                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      {agent.name}
                      {agent.isGroup && agent.groupSize && (
                        <span className="text-xs text-[var(--text-secondary)] ml-1">
                          × {agent.groupSize}
                        </span>
                      )}
                    </div>
                    {agent.description && (
                      <div className="text-xs text-[var(--text-tertiary)] max-w-[220px] truncate">
                        {agent.description}
                      </div>
                    )}
                  </div>

                  <div className="flex-shrink-0 text-xs font-medium text-[var(--text-secondary)]">
                    {getAgentStateLabel(state)}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Status message for queued state */}
      {currentStep === "queued" && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="p-3 rounded-lg bg-yellow-50/50 dark:bg-yellow-950/30 border border-yellow-200/50 dark:border-yellow-800/50"
        >
          <p className="text-xs text-yellow-700 dark:text-yellow-300">
            Your task is queued — it will start shortly.
          </p>
        </motion.div>
      )}
    </div>
  );
}
