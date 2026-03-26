"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "upgrade" | "default" | "outline";
type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--text-primary)] text-[var(--bg-base)] border border-transparent hover:opacity-90 hover:shadow-md focus-visible:ring-[var(--border-strong)] transition-all",
  default:
    "bg-[var(--text-primary)] text-[var(--bg-base)] border border-transparent hover:opacity-90 hover:shadow-md focus-visible:ring-[var(--border-strong)] transition-all",
  secondary:
    "bg-transparent text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-hover)] focus-visible:ring-[var(--border-strong)] transition-all",
  outline:
    "bg-transparent text-[var(--text-primary)] border border-[var(--border-strong)] hover:bg-[var(--bg-hover)] focus-visible:ring-[var(--border-strong)] transition-all",
  danger:
    "bg-transparent text-[var(--text-danger)] border border-[var(--border-danger)] hover:bg-[var(--bg-danger)] focus-visible:ring-[var(--text-danger)] transition-all",
  ghost:
    "bg-transparent text-[var(--text-secondary)] border border-transparent hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:ring-[var(--border-strong)] transition-all",
  upgrade:
    "bg-[var(--text-primary)] text-[var(--bg-base)] border border-transparent hover:opacity-90 hover:shadow-md focus-visible:ring-[var(--border-strong)] transition-all",
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
