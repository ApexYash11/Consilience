'use client'

import { motion } from 'framer-motion'
import { Card } from '@/components/ui'
import { Brain, Zap, Shield, TrendingUp } from 'lucide-react'

// --- Framer Motion Variants ---
const fadeDown = {
  hidden: { opacity: 0, y: -20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } }
}

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } }
}

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
    <section className="relative py-20 md:py-32 px-4 sm:px-6 lg:px-8 bg-background overflow-hidden">
      <div className="mx-auto max-w-7xl">
        {/* Section Header */}
        <div className="text-center flex flex-col items-center space-y-4 mb-16">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.15 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0 } }
            }}
          >
            <h2
              className="text-3xl md:text-4xl lg:text-5xl font-light"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Powerful Features
            </h2>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.15 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0.12 } }
            }}
          >
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
              Everything you need for deep research and analysis
            </p>
          </motion.div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature, index) => {
            const Icon = feature.icon
            return (
              <motion.div
                key={feature.title}
                initial="hidden"
                whileInView="visible"
                whileHover={{ y: -6 }}
                viewport={{ once: false, amount: 0.15 }}
                variants={{
                  hidden: { opacity: 0, y: 30 },
                  visible: { 
                    opacity: 1, 
                    y: 0, 
                    transition: { 
                      duration: 0.5, 
                      delay: index * 0.12, 
                      ease: 'easeOut' 
                    } 
                  }
                }}
              >
                <Card className="h-full p-6 transition-colors border-border hover:border-border-strong hover:shadow-md bg-card">
                  <div className="flex gap-4">
                    <div className="flex-shrink-0">
                      <div className="h-12 w-12 rounded-lg bg-muted/60 border border-border flex items-center justify-center">
                        <Icon className="h-6 w-6 text-primary" />
                      </div>
                    </div>
                    <div className="flex-1 space-y-2">
                      <h3 className="font-semibold text-lg text-foreground">
                        {feature.title}
                      </h3>
                      <p className="text-muted-foreground leading-relaxed text-sm">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
