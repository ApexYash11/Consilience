"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import { Shell } from "@/components/layout"
import { Button, Card, Input } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useAuth } from "@/context/AuthContext"

export default function Dashboard() {
  const router = useRouter()
  const { usage, logout, refreshUsage, error } = useAuth()

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  const usageSummary = useMemo(() => {
    if (!usage) {
      return []
    }

    return [
      { label: "Standard Remaining", value: `${usage.standard_research.remaining}/${usage.standard_research.quota}` },
      { label: "Deep Remaining", value: `${usage.deep_research.remaining}/${usage.deep_research.quota}` },
      { label: "Tokens This Month", value: usage.tokens_this_month.toLocaleString() },
      { label: "Cost This Month", value: `$${usage.cost_this_month_usd.toFixed(2)}` },
    ]
  }, [usage])

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
              <Button type="button" onClick={handleLogout} variant="ghost">
                Logout
              </Button>
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-lg font-semibold">Usage Summary</h2>
            <div className="space-y-3">
              {usageSummary.map((item) => (
                <div key={item.label} className="flex justify-between items-center text-sm">
                  <span className="text-[var(--text-secondary)]">{item.label}</span>
                  <span 
                    className="font-mono"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </Shell>
    </ProtectedRoute>
  )
}
