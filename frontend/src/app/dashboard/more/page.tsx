"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { Shell } from "@/components/layout"
import { Button, Card } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useAuth } from "@/context/AuthContext"
import { Home, Search, Zap, Settings, LogOut, ChevronRight } from "lucide-react"

export default function MorePage() {
  const { logout } = useAuth()
  const router = useRouter()

  const menuItems = [
    { label: "Dashboard", href: "/dashboard", icon: Home },
    { label: "Research", href: "/dashboard/research", icon: Search },
    { label: "Billing", href: "/dashboard/billing", icon: Zap },
    { label: "Settings", href: "/dashboard/settings", icon: Settings },
  ]

  const handleLogout = () => {
    logout()
    router.push("/login")
  }

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[600px] mx-auto space-y-4">
          <div className="space-y-2 mb-6">
            <h1 className="text-2xl font-semibold">Menu</h1>
            <p className="text-[var(--text-secondary)]">Navigate to other sections</p>
          </div>

          <div className="space-y-2">
            {menuItems.map(({ label, href, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="w-full p-4 flex items-center justify-between rounded-lg hover:bg-[var(--bg-hover)] transition-colors text-left hover:no-underline"
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-5 w-5 text-[var(--text-secondary)]" />
                  <span className="font-medium">{label}</span>
                </div>
                <ChevronRight className="h-5 w-5 text-[var(--text-tertiary)]" />
              </Link>
            ))}
          </div>

          <div className="my-4 border-t border-[var(--border-default)]" />

          <button
            onClick={handleLogout}
            className="w-full p-4 flex items-center gap-3 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors text-left text-red-600 dark:text-red-400"
          >
            <LogOut className="h-5 w-5" />
            <span className="font-medium">Logout</span>
          </button>
        </div>
      </Shell>
    </ProtectedRoute>
  )
}
