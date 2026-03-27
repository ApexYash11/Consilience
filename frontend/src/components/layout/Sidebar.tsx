"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { Home, Search, Settings, LogOut, Zap } from "lucide-react";
import { cn } from "@/lib/cn";
import { useAuth } from "@/context/AuthContext";

type SidebarProps = {
  open?: boolean;
  onClose?: () => void;
};

export function Sidebar({ open = true, onClose }: SidebarProps) {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = () => {
    logout();
    router.push("/login");
    onClose?.();
  };

  const dashboardNavItems = [
    { label: "Dashboard", href: "/dashboard", icon: Home },
    { label: "Research", href: "/dashboard/research", icon: Search },
    { label: "Billing", href: "/dashboard/billing", icon: Zap },
    { label: "Settings", href: "/dashboard/settings", icon: Settings },
  ];

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 w-[200px] border-r border-[var(--border-default)] bg-[var(--bg-sidebar)]",
        "md:static md:z-auto",
        !open && "hidden md:block"
      )}
      style={{ top: "48px" }}
    >
      <nav className="space-y-1 p-3 pt-4">
        {isAuthenticated ? (
          <>
            {dashboardNavItems.map(({ label, href, icon: Icon }) => (
              <Link key={href} href={href}>
                <button
                  type="button"
                  aria-current={isActive(href) ? "page" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-[var(--r-md)] px-3 py-2 text-sm transition-colors",
                    isActive(href)
                      ? "bg-[var(--bg-active)] text-[var(--text-primary)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{label}</span>
                </button>
              </Link>
            ))}

            {/* Divider */}
            <div className="my-2 border-t border-[var(--border-default)]" />

            {/* Logout button */}
            <button
              type="button"
              onClick={handleLogout}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-[var(--r-md)] px-3 py-2 text-sm transition-colors",
                "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-red-500"
              )}
            >
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </button>
          </>
        ) : (
          <p className="px-3 py-2 text-xs text-[var(--text-tertiary)]">
            Sign in to access dashboard
          </p>
        )}
      </nav>
    </aside>
  );
}
