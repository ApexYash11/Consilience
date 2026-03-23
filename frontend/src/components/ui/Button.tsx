"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "upgrade";
type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--blue-400)] text-white border border-[#2563eb] hover:bg-[#3b82f6] hover:shadow-md focus-visible:ring-[var(--blue-400)] transition-all",
  secondary:
    "bg-transparent text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-hover)] hover:border-[var(--border-strong)] focus-visible:ring-[var(--blue-400)] transition-all",
  danger:
    "bg-transparent text-[var(--text-danger)] border border-[var(--border-danger)] hover:bg-[var(--bg-danger)] hover:border-[var(--text-danger)] focus-visible:ring-[var(--text-danger)] transition-all",
  ghost:
    "bg-transparent text-[var(--text-secondary)] border border-transparent hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:ring-[var(--blue-400)] transition-all",
  upgrade:
    "bg-[#7c3aed] text-white border border-[#6d28d9] hover:bg-[#a855f7] hover:shadow-md focus-visible:ring-[#7c3aed] transition-all",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 text-[13px]",
  lg: "h-10 px-5 text-sm",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className,
  children,
  ...props
}: Props) {
  const isDisabled = disabled || loading;

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--r-md)] font-medium transition duration-100 ease-out active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 disabled:opacity-40 disabled:cursor-not-allowed",
        "min-h-11 md:min-h-0",
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      disabled={isDisabled}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  );
}
