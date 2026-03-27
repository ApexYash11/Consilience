"use client"

import { Shell } from "@/components/layout"
import { Card } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[1200px] mx-auto space-y-6">
          <div className="space-y-2">
            <h1 className="text-3xl md:text-4xl" style={{ fontFamily: "var(--font-display)", fontWeight: 400 }}>
              Settings
            </h1>
            <p className="text-[var(--text-secondary)]">
              Manage your account preferences and settings
            </p>
          </div>

          <Card className="p-6">
            <div className="text-center py-12">
              <p className="text-[var(--text-secondary)] text-lg">
                Settings page coming soon
              </p>
              <p className="text-[var(--text-tertiary)] mt-2">
                Account preferences, notifications, and more will be available here.
              </p>
            </div>
          </Card>
        </div>
      </Shell>
    </ProtectedRoute>
  )
}
