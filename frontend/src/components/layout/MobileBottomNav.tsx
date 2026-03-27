"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Search, Zap, Settings, MoreVertical } from "lucide-react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/context/AuthContext";

export function MobileBottomNav() {
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();

  if (!isAuthenticated) {
    return null; // Hide for non-authenticated users
  }

  const navItems = [
    { label: "Dashboard", href: "/dashboard", icon: Home },
    { label: "Research", href: "/dashboard/research", icon: Search },
    { label: "Billing", href: "/dashboard/billing", icon: Zap },
    { label: "Settings", href: "/dashboard/settings", icon: Settings },
    { label: "More", href: "/dashboard/more", icon: MoreVertical },
  ];

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 border-t border-[var(--border-default)] bg-[var(--bg-surface)] md:hidden">
      <div className="flex h-16 items-center justify-around">
        {navItems.map(({ label, href, icon: Icon }) => (
          <Link key={href} href={href} className="flex-1">
            <button
              type="button"
              aria-current={isActive(href) ? "page" : undefined}
              className={cn(
                "flex h-full w-full flex-col items-center justify-center gap-1 text-xs transition-colors",
                isActive(href)
                  ? "text-[var(--text-primary)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              )}
              title={label}
            >
              <Icon className="h-5 w-5" />
              <span className="truncate">{label}</span>
            </button>
          </Link>
        ))}
      </div>
    </nav>
  );
}
