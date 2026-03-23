"use client";

import { useMemo } from "react";
import { Shell } from "@/components/layout";
import { Button, Card, Input } from "@/components/ui";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { usage, logout, refreshUsage, error } = useAuth();
  const usageSummary = useMemo(() => {
    if (!usage) {
      return [];
    }

    return [
      { label: "Standard Remaining", value: `${usage.standard_research.remaining}/${usage.standard_research.quota}` },
      { label: "Deep Remaining", value: `${usage.deep_research.remaining}/${usage.deep_research.quota}` },
      { label: "Tokens This Month", value: usage.tokens_this_month.toLocaleString() },
      { label: "Cost This Month", value: `$${usage.cost_this_month_usd.toFixed(2)}` },
    ];
  }, [usage]);

  return (
    <ProtectedRoute>
      <Shell>
        <div className="mx-auto grid w-full max-w-[980px] gap-4 md:grid-cols-2">
          <Card>
            <h1
              className="mb-1 text-[28px]"
              style={{ fontFamily: "var(--font-display)", fontWeight: 400, lineHeight: 1.2 }}
            >
              Research Dashboard
            </h1>
            <p className="mb-4 text-[var(--text-secondary)]">
              Auth foundation is live. Next step is wiring standard/deep research create and status polling.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={() => void refreshUsage()} variant="secondary">
                Refresh Usage
              </Button>
              <Button type="button" variant="upgrade">
                Upgrade Plan
              </Button>
              <Button type="button" variant="ghost" onClick={logout}>
                Sign Out
              </Button>
            </div>
            {error ? <p className="mt-3 text-xs text-[var(--text-danger)]">{error}</p> : null}
          </Card>

          <Card>
            <h2 className="mb-3 text-xl font-medium">Usage Snapshot</h2>
            {usage ? (
              <div className="grid grid-cols-2 gap-2">
                {usageSummary.map((item) => (
                  <div key={item.label} className="rounded-[var(--r-md)] bg-[var(--bg-sunken)] p-3">
                    <p className="text-[11px] text-[var(--text-tertiary)]">{item.label}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">No usage loaded yet.</p>
            )}
          </Card>

          <Card className="md:col-span-2">
            <h2 className="mb-3 text-xl font-medium">Create Research</h2>
            <div className="grid gap-3 md:grid-cols-2">
              <Input
                label="Research Topic"
                placeholder="What would you like to research?"
                helperText="Minimum 10 characters"
              />
              <Input label="Budget Limit" placeholder="$0.10" helperText="Optional: use numeric format" />
            </div>
            <div className="mt-3 flex gap-2">
              <Button type="button" size="lg">
                Start Research
              </Button>
              <Button type="button" size="lg" variant="ghost">
                Save Draft
              </Button>
            </div>
          </Card>
        </div>
      </Shell>
    </ProtectedRoute>
  );
}
