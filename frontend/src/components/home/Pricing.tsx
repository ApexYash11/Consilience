'use client'

import Link from 'next/link'
import { Card } from '@/components/ui'
import { Button } from '@/components/ui'
import { Check } from 'lucide-react'

const plans = [
  {
    name: 'Standard',
    description: 'For individuals and small teams',
    price: '9',
    billing: 'per month',
    cta: 'Get Started',
    features: [
      'Unlimited standard research',
      '5 deep research queries/month',
      'Source tracking and citations',
      'CSV export',
      'Email support',
      'Standard API access',
    ],
  },
  {
    name: 'Deep Research Pro',
    description: 'For serious researchers',
    price: '29',
    billing: 'per month',
    cta: 'Upgrade Now',
    popular: true,
    features: [
      'Unlimited standard research',
      'Unlimited deep research',
      'Advanced citations and sources',
      'CSV & JSON export',
      'Priority support',
      'Full API access',
      'Custom research parameters',
      'Batch API requests',
    ],
  },
]

export function Pricing() {
  return (
    <section className="relative py-20 md:py-32 px-4 sm:px-6 lg:px-8 bg-muted/40">
      <div className="mx-auto max-w-7xl">
        {/* Section Header */}
        <div className="text-center space-y-4 mb-16">
          <h2
            className="text-3xl md:text-4xl lg:text-5xl font-light"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Simple, Transparent Pricing
          </h2>
          <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
            Choose the plan that fits your research needs
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={`relative p-8 transition-all ${
                plan.popular
                  ? 'ring-2 ring-primary md:scale-105'
                  : ''
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="inline-block bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-semibold">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="space-y-6">
                {/* Plan Name */}
                <div>
                  <h3 className="text-2xl font-semibold">{plan.name}</h3>
                  <p className="text-muted-foreground mt-1">{plan.description}</p>
                </div>

                {/* Price */}
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-5xl font-light" style={{ fontFamily: "var(--font-mono)" }}>
                      ${plan.price}
                    </span>
                    <span className="text-muted-foreground">{plan.billing}</span>
                  </div>
                </div>

                {/* CTA Button */}
                <Link href="/register" className="block">
                  <Button
                    className="w-full"
                    variant={plan.popular ? 'default' : 'outline'}
                  >
                    {plan.cta}
                  </Button>
                </Link>

                {/* Features */}
                <div className="space-y-3 pt-4 border-t border-border">
                  {plan.features.map((feature) => (
                    <div key={feature} className="flex items-start gap-3">
                      <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                      <span className="text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-16 text-center">
          <p className="text-muted-foreground mb-4">Questions? Check our</p>
          <Link href="/docs/pricing" className="text-primary hover:underline font-medium">
            pricing FAQ →
          </Link>
        </div>
      </div>
    </section>
  )
}
