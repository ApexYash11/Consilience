import type { ReactNode } from "react";
import { Home, Search, Settings, User } from "lucide-react";
import { cn } from "@/lib/cn";

type ShellProps = {
  children: ReactNode;
};

const navItems = [
  { label: "Home", icon: Home, active: true },
  { label: "Research", icon: Search },
  { label: "Settings", icon: Settings },
  { label: "Account", icon: User },
];

export function Shell({ children }: ShellProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
      <header className="sticky top-0 z-20 h-12 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
        <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between">
          <p className="text-sm font-medium">Consilience</p>
          <p className="text-xs text-[var(--text-tertiary)]">Frontend Phase 0</p>
        </div>
      </header>

      <div className="mx-auto grid min-h-[calc(100vh-48px)] max-w-[1280px] grid-cols-1 md:grid-cols-[216px_1fr]">
        <aside className="hidden border-r border-[var(--border-default)] bg-[var(--bg-sidebar)] md:block">
          <nav className="p-3">
            <ul className="space-y-1">
              {navItems.map(({ label, icon: Icon, active }) => (
                <li key={label}>
                  <button
                    type="button"
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-[var(--r-md)] px-3 py-2 text-sm",
                      active
                        ? "bg-[var(--bg-active)] text-[var(--text-primary)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main className="p-4 md:p-5">{children}</main>
      </div>
    </div>
  );
}
