'use client'

import Link from 'next/link'
import { Button } from '@/components/ui'
import { ArrowRight } from 'lucide-react'
import {
  LandingSection,
  LandingSectionHeadline,
  LandingSectionSubtext,
  LandingSectionCTA,
} from '@/components/landing'

export function Hero() {
  return (
    <LandingSection className="relative min-h-[calc(100vh-64px)] pt-20 overflow-hidden">
      {/* Subtle background gradient - neutral */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-20 right-0 h-96 w-96 bg-gradient-to-br from-neutral-200/10 to-transparent dark:from-neutral-800/10 rounded-full blur-3xl" />
        <div className="absolute bottom-40 left-0 h-96 w-96 bg-gradient-to-tr from-neutral-200/10 to-transparent dark:from-neutral-800/10 rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-8">
          {/* Badge */}
          <LandingSectionHeadline className="inline-flex">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-1.5">
              <span className="text-xs font-medium text-secondary-foreground">Now Available</span>
            </div>
          </LandingSectionHeadline>

          {/* Headline */}
          <LandingSectionHeadline>
            <h1
              className="text-4xl md:text-6xl lg:text-7xl font-light leading-tight tracking-tight"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Research Intelligence
              <br />
              <span className="text-text-brand">Reimagined</span>
            </h1>
          </LandingSectionHeadline>

          {/* Subheadline */}
          <LandingSectionSubtext>
            <p className="mx-auto max-w-2xl text-lg md:text-xl text-muted-foreground leading-relaxed">
              Consilience combines deep research capabilities with intuitive design.
              Understand complex topics faster with AI-powered analysis and visual insights.
            </p>
          </LandingSectionSubtext>

          {/* CTA Buttons */}
          <LandingSectionCTA>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <Link href="/register">
                <Button size="lg" className="px-8 landing-button-hover">
                  Get Started Free
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button variant="outline" size="lg" className="px-8 landing-button-hover">
                  View Pricing
                </Button>
              </Link>
            </div>
          </LandingSectionCTA>

          {/* Trust Badge */}
          <div className="pt-12 text-center">
            <p className="text-xs text-muted-foreground mb-3">TRUSTED BY RESEARCHERS</p>
            <div className="flex items-center justify-center gap-8">
              <div className="h-8 bg-muted rounded px-3 flex items-center text-sm font-medium text-muted-foreground">
                Company
              </div>
              <div className="h-8 bg-muted rounded px-3 flex items-center text-sm font-medium text-muted-foreground">
                Company
              </div>
              <div className="h-8 bg-muted rounded px-3 flex items-center text-sm font-medium text-muted-foreground">
                Company
              </div>
            </div>
          </div>
        </div>
      </div>
    </LandingSection>
  )
}
