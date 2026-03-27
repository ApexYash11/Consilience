'use client'

import { useState } from 'react'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import { Card } from '@/components/ui'
import { Button } from '@/components/ui'
import { Check } from 'lucide-react'
import {
  LandingSectionHeadline,
  LandingSectionSubtext,
} from '@/components/landing'

const priceSwap = {
  initial: { opacity: 0, y: -20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: 20, transition: { duration: 0.2 } },
}

const plans = [
  {
    name: 'Free',
    price: { monthly: '0', yearly: '0' },
    billing: '/ month',
    cta: 'Start Free',
    popular: false,
    features: [
      '5 standard research tasks/mo',
      'Source verification',
      'Hallucination detection',
      'Basic citations',
      'Community support',
    ],
  },
  {
    name: 'Standard',
    price: { monthly: '9', yearly: '8' },
    billing: '/ month',
    cta: 'Upgrade to Standard',
    popular: true,
    features: [
      'Unlimited standard research',
      '5 deep research tasks/mo',
      'Source tracking & citations',
      'CSV export',
      'Email support',
      'Standard API access',
    ],
  },
  {
    name: 'Deep Research Pro',
    price: { monthly: '29', yearly: '24' },
    billing: '/ month',
    cta: 'Get Pro',
    popular: false,
    features: [
      'Unlimited standard research',
      'Unlimited deep research',
      'Advanced citations & sources',
      'CSV & JSON export',
      'Priority support',
      'Full API access',
      'Custom research parameters',
    ],
  },
]

export function Pricing() {
  const [isYearly, setIsYearly] = useState(false)

  return (
    <section className="relative py-20 md:py-32 px-4 sm:px-6 lg:px-8 overflow-hidden flex flex-col items-center">
      <div className="mx-auto max-w-7xl w-full">
        {/* Section Header */}
        <div className="text-center flex flex-col items-center mb-16">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0 } }
            }}
          >
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground mb-8">
              No credit card required. Upgrade only when you need more.
            </p>
          </motion.div>

          {/* Billing Toggle */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
            variants={{
              hidden: { opacity: 0, y: -20 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.5, delay: 0.12 } }
            }}
            className="inline-flex items-center p-1 rounded-full border border-border bg-background shadow-sm"
            role="radiogroup"
            aria-label="Billing frequency"
          >
            <button
              onClick={() => setIsYearly(false)}
              role="radio"
              aria-checked={!isYearly}
              aria-label="Monthly billing"
              className={`relative px-6 py-2 rounded-full text-sm font-medium transition-colors ${
                !isYearly ? 'text-primary-foreground' : 'text-muted-foreground hover:text-primary'
              }`}
            >
              {!isYearly && (
                <motion.div
                  layoutId="billing-pill"
                  className="absolute inset-0 bg-primary rounded-full"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                />
              )}
              <span className="relative z-10">Monthly</span>
            </button>
            <button
              onClick={() => setIsYearly(true)}
              role="radio"
              aria-checked={isYearly}
              aria-label="Yearly billing, 15% off"
              className={`relative px-6 py-2 rounded-full text-sm font-medium transition-colors ${
                isYearly ? 'text-primary-foreground' : 'text-muted-foreground hover:text-primary'
              }`}
            >
              {isYearly && (
                <motion.div
                  layoutId="billing-pill"
                  className="absolute inset-0 bg-primary rounded-full"
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                />
              )}
              <span className="relative z-10">Yearly 15% off</span>
            </button>
          </motion.div>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 items-start max-w-6xl mx-auto pt-8">
          {plans.map((plan, cardIndex) => (
            <motion.div
              key={plan.name}
              initial="hidden"
              whileInView="visible"
              whileHover={{ y: -6 }}
              viewport={{ once: true, amount: 0.15 }}
              variants={{
                hidden: { opacity: 0, y: 30 },
                visible: { 
                  opacity: 1, 
                  y: 0, 
                  transition: { 
                    duration: 0.5, 
                    delay: cardIndex * 0.12,
                    ease: 'easeOut'
                  } 
                }
              }}
              className={`relative flex flex-col h-full ${plan.popular ? 'md:-mt-8 z-10' : 'mt-4'}`}
            >
              {plan.popular && (
                <div className="bg-primary/20 text-primary uppercase tracking-wide text-xs font-semibold py-3 text-center rounded-t-[var(--r-xl)] border-x border-t border-primary/30 shadow-lg">
                  Popular
                </div>
              )}

              <Card
                className={`flex-1 flex flex-col p-8 transition-all duration-300 ${
                  plan.popular
                    ? 'ring-2 ring-primary shadow-xl rounded-t-none bg-background'
                    : 'bg-background hover:shadow-lg border-border'
                }`}
              >
                <div className="space-y-6 flex-1">
                  {/* Plan Name */}
                  <div className="mb-2">
                    <h3 className="text-xl font-medium text-muted-foreground">{plan.name}</h3>
                  </div>

                  {/* Price */}
                  <div className="mb-6 h-[60px] flex items-baseline gap-2">
                    <span className="text-5xl font-semibold" style={{ fontFamily: "var(--font-mono)" }}>
                      $
                    </span>
                    <div className="relative h-[60px] overflow-hidden leading-none">
                      <AnimatePresence mode="wait">
                        <motion.span
                          key={isYearly ? 'yearly' : 'monthly'}
                          variants={priceSwap}
                          initial="initial"
                          animate="animate"
                          exit="exit"
                          className="inline-block text-5xl font-semibold"
                          style={{ fontFamily: "var(--font-display)" }}
                        >
                          {isYearly ? plan.price.yearly : plan.price.monthly}
                        </motion.span>
                      </AnimatePresence>
                    </div>
                    <span className="text-muted-foreground text-base ml-1">{plan.billing}</span>
                  </div>

                  {/* Features */}
                  <div className="space-y-4 pt-6">
                    {plan.features.map((feature, featureIndex) => (
                      <motion.div 
                        key={feature} 
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, amount: 0.15 }}
                        variants={{
                          hidden: { opacity: 0, x: -15 },
                          visible: { 
                            opacity: 1, 
                            x: 0, 
                            transition: { 
                              duration: 0.4, 
                              delay: (cardIndex * 0.12) + (featureIndex * 0.06),
                              ease: 'easeOut'
                            } 
                          }
                        }}
                        className="flex items-center gap-3"
                      >
                        <div className="rounded-full bg-muted/60 p-0.5 border border-border">
                          <Check className="h-4 w-4 text-primary flex-shrink-0" />
                        </div>
                        <span className="text-sm text-foreground/90">{feature}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>

                {/* CTA Button */}
                <motion.div
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, amount: 0.15 }}
                  variants={{
                    hidden: { opacity: 0, y: 20 },
                    visible: { 
                      opacity: 1, 
                      y: 0, 
                      transition: { 
                        delay: (cardIndex * 0.12) + (plan.features.length * 0.06) + 0.1,
                        duration: 0.4 
                      } 
                    }
                  }}
                  className="mt-8 pt-4 w-full block"
                >
                  <Link href="/register" className="w-full block">
                    <motion.div whileTap={{ scale: 0.97 }}>
                      <Button
                        className="w-full h-12 rounded-lg font-medium"
                        variant={plan.popular ? 'default' : 'outline'}
                      >
                        {plan.cta}
                      </Button>
                    </motion.div>
                  </Link>
                </motion.div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
