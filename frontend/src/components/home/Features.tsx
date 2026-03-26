'use client'

import { Card } from '@/components/ui'
import { Brain, Zap, Shield, TrendingUp } from 'lucide-react'
import {
  LandingSection,
  LandingSectionHeadline,
  LandingSectionSubtext,
} from '@/components/landing'

const features = [
  {
    icon: Brain,
    title: 'Deep Research',
    description: 'Get comprehensive analysis with citations and source tracking for complex questions.',
  },
  {
    icon: Zap,
    title: 'Standard Research',
    description: 'Quick answers with relevant sources. Perfect for everyday research needs.'
  },
  {
    icon: Shield,
    title: 'Privacy First',
    description: 'Your data is encrypted and never used for model training. Complete privacy guaranteed.',
  },
  {
    icon: TrendingUp,
    title: 'Analytics Dashboard',
    description: 'Track your research usage, costs, and insights with detailed analytics.',
  },
]

export function Features() {
  return (
    <LandingSection className="relative py-20 md:py-32 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        {/* Section Header */}
        <div className="text-center space-y-4 mb-16">
          <LandingSectionHeadline>
            <h2
              className="text-3xl md:text-4xl lg:text-5xl font-light"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Powerful Features
            </h2>
          </LandingSectionHeadline>
          <LandingSectionSubtext>
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
              Everything you need for deep research and analysis
            </p>
          </LandingSectionSubtext>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <LandingSectionSubtext key={feature.title}>
                <Card className="p-6 hover:border-primary/50 transition-colors">
                  <div className="flex gap-4">
                    <div className="flex-shrink-0">
                      <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Icon className="h-6 w-6 text-primary" />
                      </div>
                    </div>
                    <div className="flex-1 space-y-2">
                      <h3 className="font-semibold text-lg">
                        {feature.title}
                      </h3>
                      <p className="text-muted-foreground">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </Card>
              </LandingSectionSubtext>
            )
          })}
        </div>
      </div>
    </LandingSection>
  )
}
