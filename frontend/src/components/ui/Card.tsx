import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Props = HTMLAttributes<HTMLDivElement>;

export function Card({ className, children, ...props }: Props) {
  return (
    <div
      className={cn(
        "rounded-[var(--r-lg)] border border-[var(--border-default)]",
        "bg-[var(--bg-surface)] p-4 shadow-[var(--shadow-card)]",
        "dark:shadow-none",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
