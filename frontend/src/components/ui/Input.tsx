"use client";

import { useId, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  helperText?: string;
  error?: string;
};

export function Input({ label, helperText, error, className, id, ...props }: Props) {
  const autoId = useId();
  const labelId = label?.toLowerCase().replace(/\s+/g, "-");
  const fallbackId = `input-${autoId.replace(/:/g, "")}`;
  const inputId = id ?? labelId ?? fallbackId;
  const describedBy = error ? `${inputId}-error` : helperText ? `${inputId}-help` : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={inputId} className="text-xs font-medium text-[var(--text-secondary)]">
          {label}
        </label>
      ) : null}

      <input
        id={inputId}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={cn(
          "h-11 md:h-9 w-full rounded-[var(--r-md)] border border-[var(--border-default)]",
          "bg-[var(--bg-surface)] px-3 text-base md:text-[13px] text-[var(--text-primary)]",
          "placeholder:text-[var(--text-muted)]",
          "focus:outline-none focus:ring-2 focus:ring-[var(--blue-400)] focus:border-[var(--blue-400)]",
          error
            ? "border-[1.5px] border-[var(--text-danger)] focus:ring-[var(--text-danger)]/25"
            : "hover:border-[var(--border-strong)]",
          className
        )}
        {...props}
      />

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
