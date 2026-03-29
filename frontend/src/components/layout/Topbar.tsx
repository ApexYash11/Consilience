"use client";

import Link from "next/link";
import { Menu, X, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cn";

type TopbarProps = {
  mobileSidebarOpen: boolean;
  onMobileSidebarToggle: () => void;
  isDarkMode: boolean;
  onThemeToggle: () => void;
};

export function Topbar({
  mobileSidebarOpen,
  onMobileSidebarToggle,
  isDarkMode,
  onThemeToggle,
}: TopbarProps) {
  return (
    <header className="sticky top-0 z-50 h-12 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
      <div className="flex h-full items-center justify-between px-4">
        {/* Left: Logo + Mobile Menu Toggle */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onMobileSidebarToggle}
            className="md:hidden"
            aria-label="Toggle sidebar"
          >
            {mobileSidebarOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
          <Link href="/" className="font-semibold text-sm">
            Consilience
          </Link>
        </div>

        {/* Right: Theme Toggle */}
        <button
          type="button"
          onClick={onThemeToggle}
          className={cn(
            "rounded-md p-2 transition-colors",
            "hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          )}
          aria-label="Toggle theme"
        >
          {isDarkMode ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
      </div>
    </header>
  );
}
