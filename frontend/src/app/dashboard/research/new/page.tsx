"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Loader, AlertCircle } from "lucide-react";
import { Shell } from "@/components/layout";
import { Button, Card, Input } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { cn } from "@/lib/cn";

export default function NewResearchPage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [depth, setDepth] = useState<"standard" | "deep">("standard");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!topic.trim()) {
      setError("Please enter a research topic");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem("consilience_access_token");
      if (!token) {
        setError("Not authenticated. Please log in again.");
        router.push("/login");
        return;
      }

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const endpoint = depth === "deep" ? "/api/research/deep" : "/api/research/standard";

      const response = await fetch(`${apiUrl}${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          topic: topic.trim(),
          requirements: {},
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          data.detail || data.message || `Failed to create research (${response.status})`
        );
      }

      const result: { task_id: string } = await response.json();

      // Redirect to status page
      router.push(`/dashboard/research/${result.task_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error occurred";
      setError(message);
      setIsLoading(false);
    }
  };

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[600px] mx-auto space-y-6">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3"
          >
            <Button
              onClick={() => router.back()}
              variant="ghost"
              size="sm"
              disabled={isLoading}
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-3xl md:text-4xl font-medium">New Research</h1>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Start a new research task
              </p>
            </div>
          </motion.div>

          {/* Form Card */}
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="p-6">
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Topic Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-[var(--text-primary)]">
                    Research Topic
                  </label>
                  <Input
                    type="text"
                    placeholder="e.g., Climate change impacts on agriculture"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    disabled={isLoading}
                    className="w-full"
                  />
                  <p className="text-xs text-[var(--text-tertiary)]">
                    Describe what you&apos;d like to research
                  </p>
                </div>

                {/* Research Depth */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-[var(--text-primary)]">
                    Research Depth
                  </label>

                  <div className="space-y-2">
                    {/* Standard */}
                    <button
                      type="button"
                      onClick={() => setDepth("standard")}
                      disabled={isLoading}
                      className={cn(
                        "w-full p-4 rounded-lg border text-left transition-all",
                        depth === "standard"
                          ? "border-blue-400/50 bg-blue-50/50 dark:bg-blue-950/30"
                          : "border-[var(--border-default)] bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-[var(--text-primary)]">
                            Standard Research
                          </div>
                          <div className="text-xs text-[var(--text-tertiary)] mt-1">
                            5-10 minutes • ~$0.10 • 5 parallel researchers
                          </div>
                        </div>
                        <div
                          className={cn(
                            "h-5 w-5 rounded border-2 flex items-center justify-center",
                            depth === "standard"
                              ? "border-blue-500 bg-blue-500"
                              : "border-[var(--border-default)]"
                          )}
                        >
                          {depth === "standard" && (
                            <div className="h-2 w-2 rounded-full bg-white" />
                          )}
                        </div>
                      </div>
                    </button>

                    {/* Deep */}
                    <button
                      type="button"
                      onClick={() => setDepth("deep")}
                      disabled={isLoading}
                      className={cn(
                        "w-full p-4 rounded-lg border text-left transition-all",
                        depth === "deep"
                          ? "border-purple-400/50 bg-purple-50/50 dark:bg-purple-950/30"
                          : "border-[var(--border-default)] bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-[var(--text-primary)]">
                            Deep Research{" "}
                            <span className="text-xs font-normal text-purple-600 dark:text-purple-400">
                              (Paid)
                            </span>
                          </div>
                          <div className="text-xs text-[var(--text-tertiary)] mt-1">
                            15-30 minutes • ~$0.50 • 3 research rounds with refinement
                          </div>
                        </div>
                        <div
                          className={cn(
                            "h-5 w-5 rounded border-2 flex items-center justify-center",
                            depth === "deep"
                              ? "border-purple-500 bg-purple-500"
                              : "border-[var(--border-default)]"
                          )}
                        >
                          {depth === "deep" && (
                            <div className="h-2 w-2 rounded-full bg-white" />
                          )}
                        </div>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Error Message */}
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="p-3 rounded-lg border border-red-300/50 bg-red-50/50 dark:bg-red-950/30"
                  >
                    <div className="flex items-start gap-3">
                      <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                    </div>
                  </motion.div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-2">
                  <Button
                    onClick={() => router.back()}
                    variant="secondary"
                    className="flex-1"
                    disabled={isLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    className="flex-1"
                    disabled={isLoading}
                  >
                    {isLoading && <Loader className="h-4 w-4 mr-2 animate-spin" />}
                    {isLoading ? "Creating..." : "Start Research"}
                  </Button>
                </div>
              </form>
            </Card>
          </motion.div>

          {/* Info Box */}
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-4 rounded-lg bg-[var(--bg-hover)] border border-[var(--border-default)]"
          >
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Your research will be analyzed by 7 specialized agents working in parallel:
              Planner → Researchers → Verifier → Detector → Synthesizer → Reviewer →
              Formatter. You can monitor progress in real-time.
            </p>
          </motion.div>
        </div>
      </Shell>
    </ProtectedRoute>
  );
}
