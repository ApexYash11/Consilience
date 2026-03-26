"use client";

import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  helperText?: string;
  error?: string;
  rightElement?: ReactNode;
};

export function Input({ label, helperText, error, rightElement, className, id, ...props }: Props) {
  const autoId = useId();
  const labelId = label?.toLowerCase().replace(/\s+/g, "-");
  const fallbackId = `input-${autoId.replace(/:/g, "")}`;
  const inputId = id ?? labelId ?? fallbackId;
  const describedBy = error ? `${inputId}-error` : helperText ? `${inputId}-help` : undefined;

  return (
    <div className="flex flex-col gap-1.5 w-full">
      {label ? (
        <label htmlFor={inputId} className="text-xs font-medium text-[var(--text-secondary)]">
          {label}
        </label>
      ) : null}

      <div className="relative flex items-center w-full">
        <input
          id={inputId}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={cn(
            "h-11 md:h-9 w-full rounded-[var(--r-md)] border border-[var(--border-default)]",
            "bg-[var(--bg-surface)] px-3 text-base md:text-[13px] text-[var(--text-primary)]",
            "placeholder:text-[var(--text-muted)]",
            "focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-[var(--border-strong)] focus:border-[var(--border-strong)] transition-all",
            error
              ? "border-[1.5px] border-[var(--text-danger)] focus:ring-[var(--text-danger)] focus:ring-offset-0"
              : "hover:border-[var(--border-strong)] hover:bg-[var(--bg-surface-hover)]",
            rightElement ? "pr-10" : "",
            className
          )}
          {...props}
        />
        {rightElement && (
          <div className="absolute right-3 flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer">
            {rightElement}
          </div>
        )}
      </div>

      {error ? (
        <p id={`${inputId}-error`} className="text-xs text-[var(--text-danger)]">
          {error}
        </p>
      ) : helperText ? (
        <p id={`${inputId}-help`} className="text-xs text-[var(--text-tertiary)]">
          {helperText}
        </p>
      ) : null}
    </div>
  );
}
