'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui'
import { ArrowRight } from 'lucide-react'

export function Hero() {
  return (
    <section className="relative min-h-[calc(100vh-64px)] pt-20 overflow-hidden flex flex-col items-center">
      {/* Subtle background gradient - neutral */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-20 right-0 h-96 w-96 bg-gradient-to-br from-neutral-200/10 to-transparent dark:from-neutral-800/10 rounded-full blur-3xl" />
        <div className="absolute bottom-40 left-0 h-96 w-96 bg-gradient-to-tr from-neutral-200/10 to-transparent dark:from-neutral-800/10 rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full">
        <div className="text-center flex flex-col items-center space-y-8">
          {/* Badge */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.2 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0 } }
            }}
            className="inline-flex"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-1.5 shadow-sm">
              <span className="text-xs font-medium text-secondary-foreground">Now Available</span>
            </div>
          </motion.div>

          {/* Headline */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.2 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0.12 } }
            }}
          >
            <h1
              className="text-4xl md:text-6xl lg:text-7xl font-light leading-tight tracking-tight"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Research Intelligence
              <br />
              <span className="text-text-brand">Reimagined</span>
            </h1>
          </motion.div>

          {/* Subheadline */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.2 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0.24 } }
            }}
          >
            <p className="mx-auto max-w-2xl text-lg md:text-xl text-muted-foreground leading-relaxed">
              Consilience combines deep research capabilities with intuitive design.
              Understand complex topics faster with AI-powered analysis and visual insights.
            </p>
          </motion.div>

          {/* CTA Buttons */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.2 }}
            variants={{
              hidden: { opacity: 0, y: 20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0.36 } }
            }}
          >
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <Link href="/register" className="block">
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
                  <Button size="lg" className="px-8 shadow-sm">
                    Get Started Free
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </motion.div>
              </Link>
              <Link href="/pricing" className="block">
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
                  <Button variant="outline" size="lg" className="px-8">
                    View Pricing
                  </Button>
                </motion.div>
              </Link>
            </div>
          </motion.div>

          {/* Trust Badge */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.2 }}
            variants={{
              hidden: { opacity: 0 },
              visible: { opacity: 1, transition: { duration: 0.8, delay: 0.5 } }
            }}
            className="pt-12 text-center"
          >
            <p className="text-xs text-muted-foreground mb-3">TRUSTED BY RESEARCHERS</p>
            <div className="flex items-center justify-center gap-8 opacity-60 grayscale">
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
          </motion.div>
        </div>
      </div>
    </section>
  )
}
