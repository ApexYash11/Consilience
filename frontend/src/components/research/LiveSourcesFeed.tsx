"use client";

import { motion, AnimatePresence } from "framer-motion";
import { ExternalLink } from "lucide-react";
import type { Source } from "@/types/research";
import { cn } from "@/lib/cn";
import { useMemo } from "react";

interface LiveSourcesFeedProps {
  sources?: Source[];
  maxVisible?: number;
}

export function LiveSourcesFeed({ sources = [], maxVisible = 4 }: LiveSourcesFeedProps) {
  const animationConfig = {
    duration: 0.3,
    ease: "easeOut",
  };

  // Deduplicate sources by URL and limit visible items
  const deduplicatedSources = useMemo(() => {
    const seen = new Set<string>();
    const unique: Source[] = [];

    for (const source of sources) {
      if (!seen.has(source.url)) {
        seen.add(source.url);
        unique.push(source);
      }
    }

    return unique.slice(0, maxVisible);
  }, [sources, maxVisible]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-[var(--text-secondary)]">Sources Found</div>
        {deduplicatedSources.length > 0 && (
          <div className="text-xs text-[var(--text-tertiary)]">
            {deduplicatedSources.length} source{deduplicatedSources.length !== 1 ? "s" : ""}
            {deduplicatedSources.length > maxVisible && ` (showing ${maxVisible})`}
          </div>
        )}
      </div>

      <div className="space-y-2 min-h-[60px]">
        <AnimatePresence mode="popLayout">
          {deduplicatedSources.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="p-3 text-center text-xs text-[var(--text-tertiary)] border border-dashed border-[var(--border-default)] rounded-lg"
            >
              Waiting for sources...
            </motion.div>
          ) : (
            deduplicatedSources.map((source, idx) => (
              <motion.a
                key={source.url}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                layout
                initial={{ opacity: 0, translateY: 6 }}
                animate={{ opacity: 1, translateY: 0 }}
                exit={{ opacity: 0, translateY: 6 }}
                transition={{
                  duration: animationConfig.duration,
                  delay: idx * 0.05,
                }}
                className={cn(
                  "p-3 rounded-lg border flex items-start gap-2 transition-all",
                  "hover:bg-[var(--bg-hover)] hover:border-[var(--border-strong)]",
                  "bg-[var(--bg-surface)] border-[var(--border-default)]",
                  "group cursor-pointer"
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--text-primary)] line-clamp-2 group-hover:text-blue-500 transition-colors">
                    {source.title}
                  </div>
                  <div className="text-xs text-[var(--text-tertiary)] line-clamp-1 mt-1">
                    {source.url}
                  </div>
                  {source.qualityScore !== undefined && (
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <div className="h-1.5 w-16 bg-[var(--bg-hover)] rounded-full overflow-hidden">
                        <motion.div
                          className="h-full bg-green-500"
                          initial={{ width: 0 }}
                          animate={{
                            width: `${Math.max(0, Math.min(100, Math.round(source.qualityScore * 100)))}%`,
                          }}
                          transition={{ duration: 0.6, ease: "easeOut" }}
                        />
                      </div>
                      <span className="text-xs text-[var(--text-tertiary)]">
                        {Math.max(0, Math.min(100, Math.round(source.qualityScore * 100)))}%
                      </span>
                    </div>
                  )}
                </div>
                <ExternalLink className="h-4 w-4 flex-shrink-0 text-[var(--text-tertiary)] group-hover:text-blue-500 transition-colors mt-0.5" />
              </motion.a>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
