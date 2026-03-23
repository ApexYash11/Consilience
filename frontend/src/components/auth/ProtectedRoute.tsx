"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") {
      const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [pathname, router, status]);

  if (status !== "authenticated") {
    return (
      <div className="mx-auto max-w-[560px] rounded-[var(--r-lg)] border border-[var(--border-default)] bg-[var(--bg-surface)] p-5">
        <p className="text-sm text-[var(--text-secondary)]">Checking your session...</p>
      </div>
    );
  }

  return <>{children}</>;
}
