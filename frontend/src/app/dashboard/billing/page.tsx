"use client"

import { Shell } from "@/components/layout"
import { Card, Button } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { Check } from "lucide-react"

export default function BillingPage() {
  const handlePlanCta = (planName: string, ctaLabel: string) => {
    if (ctaLabel === "Current Plan") {
      return // Already on this plan
    }
    if (ctaLabel === "Contact Sales") {
      window.location.href = "mailto:sales@consilience.ai"
      return
    }
    if (ctaLabel === "Upgrade Now") {
      // Navigate to upgrade flow or open payment modal
      console.log(`Upgrading to ${planName}`)
      // TODO: Implement upgrade flow
    }
  }

  const plans = [
    {
      name: "Free",
      price: "$0",
      description: "Perfect for getting started",
      features: [
        "5 standard research tasks",
        "1 deep research task",
        "Community support",
        "Basic features",
      ],
      cta: "Current Plan",
      ctaVariant: "secondary" as const,
    },
    {
      name: "Pro",
      price: "$29",
      description: "For power users",
      features: [
        "Unlimited standard research",
        "10 deep research tasks per month",
        "Priority support",
        "Advanced features",
        "Export results",
      ],
      cta: "Upgrade Now",
      ctaVariant: "default" as const,
      highlighted: true,
    },
    {
      name: "Enterprise",
      price: "Custom",
      description: "For organizations",
      features: [
        "Everything in Pro",
        "Unlimited deep research",
        "Dedicated support",
        "Custom integrations",
        "SLA guarantees",
      ],
      cta: "Contact Sales",
      ctaVariant: "secondary" as const,
    },
  ]

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[1200px] mx-auto space-y-6">
          <div className="space-y-2">
            <h1 className="text-3xl md:text-4xl" style={{ fontFamily: "var(--font-display)", fontWeight: 400 }}>
              Billing Plans
            </h1>
            <p className="text-[var(--text-secondary)]">
              Choose the perfect plan for your research needs
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={`p-6 flex flex-col ${plan.highlighted ? "border-2 border-blue-500 relative" : ""}`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-blue-500 text-white px-3 py-1 rounded-full text-xs font-semibold">
                    RECOMMENDED
                  </div>
                )}
                <div className="mb-4 pt-2">
                  <h3 className="text-xl font-semibold">{plan.name}</h3>
                  <p className="text-[var(--text-secondary)] text-sm mt-1">{plan.description}</p>
                </div>

                <div className="mb-6">
                  <div className="text-3xl font-bold">{plan.price}</div>
                  <div className="text-[var(--text-tertiary)] text-xs">
                    {plan.name === "Enterprise" ? "Contact for details" : "per month"}
                  </div>
                </div>

                <ul className="space-y-3 mb-6 flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <Check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  variant={plan.ctaVariant}
                  className="w-full"
                  onClick={() => handlePlanCta(plan.name, plan.cta)}
                >
                  {plan.cta}
                </Button>
              </Card>
            ))}
          </div>
        </div>
      </Shell>
    </ProtectedRoute>
  )
}
