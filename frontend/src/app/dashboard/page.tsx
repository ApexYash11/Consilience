"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import { Shell } from "@/components/layout"
import { Button, Card, Input } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useAuth } from "@/context/AuthContext"
import { Activity, Zap, TrendingUp, DollarSign } from "lucide-react"

export default function Dashboard() {
  const router = useRouter()
  const { usage, refreshUsage, error } = useAuth()

  const statCards = useMemo(() => {
    if (!usage) {
      return []
    }

    return [
      {
        label: "Standard Research",
        value: usage.standard_research.remaining,
        total: usage.standard_research.quota,
        icon: Activity,
        color: "blue",
      },
      {
        label: "Deep Research",
        value: usage.deep_research.remaining,
        total: usage.deep_research.quota,
        icon: Zap,
        color: "purple",
      },
      {
        label: "Tokens This Month",
        value: usage.tokens_this_month.toLocaleString(),
        prefix: "",
        icon: TrendingUp,
        color: "green",
      },
      {
        label: "Cost This Month",
        value: usage.cost_this_month_usd.toFixed(2),
        prefix: "$",
        icon: DollarSign,
        color: "amber",
      },
    ]
  }, [usage])

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[1200px] mx-auto space-y-6">
          {/* Welcome Section */}
          <div className="space-y-2">
            <h1
              className="text-3xl md:text-4xl"
              style={{ fontFamily: "var(--font-display)", fontWeight: 400 }}
            >
              Welcome back
            </h1>
            <p className="text-[var(--text-secondary)]">
              Here's what's happening with your research today.
            </p>
          </div>

          {/* Stat Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((card) => {
              const Icon = card.icon
              return (
                <Card key={card.label} className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="text-[var(--text-secondary)] text-sm font-medium">
                      {card.label}
                    </div>
                    <Icon className="h-4 w-4 text-[var(--text-tertiary)]" />
                  </div>
                  <div className="space-y-1">
                    <div className="text-2xl font-semibold">
                      {card.prefix}{card.value}
                    </div>
                    {card.total != null && (
                      <div className="text-xs text-[var(--text-tertiary)]">
                        of {card.total} available
                      </div>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>

          {/* Quick Actions */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">Quick Actions</h2>
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => router.push("/dashboard/research")}
                className="w-full md:w-auto"
              >
                New Research
              </Button>
              <Button
                onClick={() => void refreshUsage()}
                variant="secondary"
                className="w-full md:w-auto"
              >
                Refresh Usage
              </Button>
              <Button
                onClick={() => router.push("/dashboard/billing")}
                variant="secondary"
                className="w-full md:w-auto"
              >
                Upgrade Plan
              </Button>
            </div>
          </div>

          {/* Recent Activity Placeholder */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold mb-4">Recent Research</h2>
            <div className="text-center py-8">
              <p className="text-[var(--text-secondary)] mb-4">
                No research tasks yet. Start by creating a new research task.
              </p>
              <Button
                onClick={() => router.push("/dashboard/research")}
              >
                Create First Research
              </Button>
            </div>
          </Card>
        </div>
      </Shell>
    </ProtectedRoute>
  )
}

