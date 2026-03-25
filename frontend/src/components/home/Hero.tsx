'use client'

import Link from 'next/link'
import { Button } from '@/components/ui'
import { ArrowRight } from 'lucide-react'

export function Hero() {
  return (
    <div className="relative min-h-[calc(100vh-64px)] pt-20 overflow-hidden">
      {/* Gradient Background */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 right-0 h-96 w-96 bg-gradient-to-br from-purple-500/20 to-transparent rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 h-96 w-96 bg-gradient-to-tr from-blue-500/20 to-transparent rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-8">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-1.5">
            <span className="text-xs font-medium text-secondary-foreground">🚀 Now Available</span>
          </div>

          {/* Headline */}
          <h1 
            className="text-4xl md:text-6xl lg:text-7xl font-light leading-tight tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Research Intelligence
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
              Reimagined
            </span>
          </h1>

          {/* Subheadline */}
          <p className="mx-auto max-w-2xl text-lg md:text-xl text-muted-foreground leading-relaxed">
            Consilience combines deep research capabilities with intuitive design. 
            Understand complex topics faster with AI-powered analysis and visual insights.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link href="/register">
              <Button size="lg" className="px-8">
                Get Started Free
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button variant="outline" size="lg" className="px-8">
                View Pricing
              </Button>
            </Link>
          </div>

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
    </div>
  )
}
